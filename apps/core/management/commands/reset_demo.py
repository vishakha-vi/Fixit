import os
import random
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.core import clock
from apps.core.models import DemoClock
from apps.locations.models import Building, Location
from apps.payments.models import WorkerPayment
from apps.payments.services import mark_paid
from apps.tickets import services, workflow
from apps.tickets.models import Reminder, Ticket

S = Ticket.Status

BUILDINGS = [
    ("Hostel A (Boys)", "HA", False, [
        ("Room 101", 1, False), ("Room 102", 1, False), ("Room 214", 2, False),
        ("Room 305", 3, False), ("Common Room", 0, True), ("Washroom - Floor 1", 1, True),
        ("Entrance Lobby", 0, True),
    ]),
    ("Hostel B (Girls)", "HB", False, [
        ("Room 110", 1, False), ("Room 208", 2, False), ("Room 312", 3, False),
        ("Laundry Room", 0, True), ("Washroom - Floor 2", 2, True),
    ]),
    ("Academic Block", "AB", False, [
        ("Lecture Hall 1", 0, True), ("Lecture Hall 2", 1, True), ("Computer Lab 1", 2, True),
        ("Physics Lab", 1, True), ("Faculty Room 12", 1, False),
    ]),
    ("Central Library", "LIB", False, [("Reading Hall", 1, True), ("Ground Floor Entrance", 0, True)]),
    ("Mess Hall", "MESS", True, [("Kitchen", 0, True), ("Dining Hall", 0, True)]),
    ("Health Centre", "HC", True, [("Medical Room 1", 0, True), ("OPD Waiting Area", 0, True)]),
    ("Admin Block", "ADM", False, [("Accounts Office", 1, False), ("Main Entrance", 0, True)]),
    ("Sports Complex", "SPC", False, [("Gym", 0, True), ("Badminton Court", 0, True)]),
]

# username, email, first, last, role, extra
USERS = [
    ("admin_demo", "admin@demo.campus.edu", "Alice", "Admin", User.Role.ADMIN,
     {"phone": "9800000001", "department": "Estate Office"}),
    ("staff_demo", "staff@demo.campus.edu", "Sunita", "Sharma", User.Role.STAFF,
     {"phone": "9800000002", "department": "Warden, Hostel B"}),
    ("student_demo", "student@demo.campus.edu", "Rahul", "Verma", User.Role.STUDENT,
     {"phone": "9800000003", "department": "B.Tech CSE, Hostel A room 214"}),
    ("priya_demo", "priya@demo.campus.edu", "Priya", "Singh", User.Role.STUDENT,
     {"phone": "9800000004", "department": "B.Sc Physics, Hostel B room 208"}),
    ("arjun_demo", "arjun@demo.campus.edu", "Arjun", "Mehta", User.Role.STUDENT,
     {"phone": "9800000005", "department": "MBA, Hostel A room 305"}),
    ("worker_demo", "worker@demo.campus.edu", "Ramesh", "Kumar", User.Role.WORKER,
     {"phone": "9800000011", "specialty": "electrical", "area": "HA", "rate_per_job": "300"}),
    ("suresh_demo", "suresh@demo.campus.edu", "Suresh", "Yadav", User.Role.WORKER,
     {"phone": "9800000012", "specialty": "plumbing", "area": "HB", "rate_per_job": "300"}),
    ("anita_demo", "anita@demo.campus.edu", "Anita", "Devi", User.Role.WORKER,
     {"phone": "9800000013", "specialty": "housekeeping", "area": "AB", "rate_per_job": "200"}),
    ("vikram_demo", "vikram@demo.campus.edu", "Vikram", "Singh", User.Role.WORKER,
     {"phone": "9800000014", "specialty": "carpentry", "area": "MESS", "rate_per_job": "275"}),
    ("imran_demo", "imran@demo.campus.edu", "Imran", "Khan", User.Role.WORKER,
     {"phone": "9800000015", "specialty": "network", "area": "LIB", "rate_per_job": "350",
      "availability": "off_duty"}),
]

# title, category, severity, building code, room, description, safety, affected
PROBLEMS = [
    ("Ceiling fan not working", "electrical", "moderate", "HA", "Room 214",
     "The ceiling fan stopped working since last night. Regulator seems fine.", False, 1),
    ("Tube light flickering", "electrical", "minor", "HB", "Room 110",
     "Tube light keeps flickering, hard to study at night.", False, 0),
    ("Water leaking from tap", "plumbing", "moderate", "HB", "Washroom - Floor 2",
     "Tap in the second cubicle does not close fully and water is wasting.", False, 6),
    ("Exposed wires near switchboard", "electrical", "critical", "HA", "Common Room",
     "Switchboard cover broke and copper wires are visible. Sparks seen once.", True, 20),
    ("Wi-Fi not working in reading hall", "network", "major", "LIB", "Reading Hall",
     "No internet on any device in the reading hall since morning.", False, 40),
    ("Broken chair in lecture hall", "carpentry", "minor", "AB", "Lecture Hall 2",
     "Two chairs in row 5 have broken backrests.", False, 2),
    ("AC not cooling", "hvac", "major", "AB", "Computer Lab 1",
     "Lab AC runs but does not cool; systems are overheating.", False, 30),
    ("Drain blocked", "plumbing", "major", "MESS", "Kitchen",
     "Kitchen floor drain is blocked and water is collecting.", True, 8),
    ("Door lock jammed", "carpentry", "moderate", "HA", "Room 305",
     "Room door lock is jammed, have to force it every time.", False, 1),
    ("Washroom needs cleaning", "housekeeping", "moderate", "HA", "Washroom - Floor 1",
     "Washroom has not been cleaned for two days.", False, 12),
    ("Window glass cracked", "civil", "moderate", "HB", "Room 312",
     "Window glass cracked after the storm; edges are sharp.", True, 1),
    ("Power socket not working", "electrical", "minor", "AB", "Faculty Room 12",
     "Wall socket behind the desk is dead.", False, 0),
    ("Mosquitoes in dining hall", "pest", "moderate", "MESS", "Dining Hall",
     "Lots of mosquitoes in the evening during dinner.", False, 50),
    ("Medical room light not working", "electrical", "major", "HC", "Medical Room 1",
     "Examination light in the medical room is not switching on.", False, 3),
    ("Treadmill belt slipping", "other", "minor", "SPC", "Gym",
     "Treadmill number 2 belt slips at higher speed.", False, 0),
    ("Washing machine leaking", "plumbing", "moderate", "HB", "Laundry Room",
     "Machine 3 leaks water from the bottom during the spin cycle.", False, 10),
    ("Projector not displaying", "electrical", "major", "AB", "Lecture Hall 1",
     "Projector powers on but shows no input from the HDMI cable.", False, 60),
    ("Entrance tiles broken", "civil", "moderate", "ADM", "Main Entrance",
     "Two floor tiles at the entrance are broken, someone may trip.", True, 15),
    ("Wi-Fi slow in hostel room", "network", "minor", "HA", "Room 101",
     "Wi-Fi speed is very low in the evenings.", False, 3),
    ("Geyser not heating", "plumbing", "major", "HA", "Washroom - Floor 1",
     "No hot water from the geyser since yesterday.", False, 15),
]

ACTIVE_FLOWS = [S.SUBMITTED, S.TRIAGED, S.ASSIGNED, S.IN_PROGRESS, S.WAITING_PARTS,
                S.REPORTED_FIXED]


class Command(BaseCommand):
    help = (
        "Reset the demo: recreate demo users, campus buildings and sample complaints. "
        "Deletes ALL complaints, reminders and payments. Requires DEMO_MODE and --yes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirmation flag required to execute demo reset.",
        )
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Only seed when there are no complaints yet (safe to run on every deploy).",
        )
        parser.add_argument(
            "--users-only",
            action="store_true",
            help="Only recreate demo users and buildings, without sample complaints.",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "DEMO_MODE", False):
            raise CommandError("Refusing to run: DEMO_MODE is disabled.")

        if not options.get("yes"):
            raise CommandError("Refusing to run: --yes flag is required.")

        if options.get("if_empty") and Ticket.objects.exists():
            self.stdout.write("Complaints already exist; demo seed skipped.")
            return

        self.password = os.environ.get("DEMO_PASSWORD", "DemoFixItPass123!")
        self.rng = random.Random(2026)

        clock.reset()
        self.stdout.write(self.style.SUCCESS("Demo clock offset reset to 0.0s."))

        with transaction.atomic():
            Ticket.objects.all().delete()
            Reminder.objects.all().delete()
            WorkerPayment.objects.all().delete()
            self.locations = self._seed_buildings()
            self.users = self._seed_users()
            if not options.get("users_only"):
                self._seed_tickets()
        clock.reset()
        if not options.get("users_only"):
            services.run_due_tasks(force=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully recreated {len(self.users)} demo users. Demo password set. "
                f"{Ticket.objects.count()} sample complaints ready."
            )
        )

    # ------------------------------------------------------------------
    def _seed_buildings(self):
        locations = {}
        for name, code, critical, rooms in BUILDINGS:
            building, _ = Building.objects.update_or_create(
                code=code, defaults={"name": name, "is_critical": critical}
            )
            for room, floor, common in rooms:
                location, _ = Location.objects.update_or_create(
                    building=building, name=room,
                    defaults={"floor": floor, "is_common_area": common},
                )
                locations[(code, room)] = location
        return locations

    def _seed_users(self):
        users = {}
        buildings = {b.code: b for b in Building.objects.all()}
        for username, email, first, last, role, extra in USERS:
            User.objects.filter(username=username).delete()
            User.objects.filter(email__iexact=email).delete()
            user = User(
                username=username,
                email=email,
                first_name=first,
                last_name=last,
                role=role,
                is_staff=role == User.Role.ADMIN,
                is_superuser=role == User.Role.ADMIN,
                phone=extra.get("phone", ""),
                department=extra.get("department", ""),
            )
            if role == User.Role.WORKER:
                user.specialty = extra["specialty"]
                user.area = buildings.get(extra["area"])
                user.rate_per_job = Decimal(extra["rate_per_job"])
                user.availability = extra.get("availability", User.Availability.ON_DUTY)
            user.apply_role_defaults()
            user.set_password(self.password)
            user.save()
            users[username] = user
            self.stdout.write(f"  Created demo user: {user.username} ({user.role})")
        return users

    # ------------------------------------------------------------------
    def _set_time(self, when):
        DemoClock.objects.update_or_create(
            id=1, defaults={"offset_seconds": (when - self.base_now).total_seconds()}
        )

    def _worker_for(self, category, building_code):
        workers = [u for u in self.users.values() if u.role == User.Role.WORKER]
        by_skill = {
            "electrical": "worker_demo", "plumbing": "suresh_demo", "housekeeping": "anita_demo",
            "carpentry": "vikram_demo", "network": "imran_demo", "civil": "vikram_demo",
            "hvac": "worker_demo", "pest": "anita_demo",
        }
        name = by_skill.get(category)
        if name:
            return self.users[name]
        local = [w for w in workers if w.area and w.area.code == building_code]
        return (local or workers)[0]

    def _seed_tickets(self):
        self.base_now = clock.now()
        rng = self.rng
        admin = self.users["admin_demo"]
        requesters = [self.users[n] for n in ("student_demo", "priya_demo", "arjun_demo",
                                              "staff_demo")]
        count = 0
        for index in range(46):
            problem = PROBLEMS[index % len(PROBLEMS)]
            title, category, severity, bcode, room, desc, safety, affected = problem
            days_ago = 21 * (1 - index / 46) + rng.uniform(-0.4, 0.4)
            days_ago = max(days_ago, 0.05)
            created = self.base_now - timedelta(days=days_ago, hours=rng.uniform(0, 6))
            if days_ago > 5:
                final = rng.choices(
                    [S.VERIFIED_FIXED, S.CLOSED_UNVERIFIED, S.REJECTED, S.CANCELLED,
                     S.WAITING_PARTS, S.IN_PROGRESS, S.ASSIGNED],
                    weights=[66, 4, 4, 3, 7, 6, 4],
                )[0]
            else:
                final = rng.choice(ACTIVE_FLOWS + ACTIVE_FLOWS + [S.VERIFIED_FIXED])

            requester = rng.choice(requesters)
            self._set_time(created)
            ticket, _ = services.create_ticket(
                created_by=requester,
                title=title,
                description=desc,
                category=category,
                severity=severity,
                location=self.locations[(bcode, room)],
                safety_flag=safety,
                affected_people=affected,
            )
            count += 1
            worker = self._worker_for(category, bcode)
            self._advance(ticket, final, created, admin, worker, requester)

        # Workers' last known positions (campus coordinates are illustrative)
        spots = {
            "worker_demo": (("HA", "Room 214"), 28.545210, 77.192640),
            "suresh_demo": (("HB", "Laundry Room"), 28.546020, 77.193410),
            "anita_demo": (("AB", "Lecture Hall 1"), 28.544480, 77.191720),
            "vikram_demo": (("MESS", "Dining Hall"), 28.545900, 77.190950),
        }
        for name, (loc_key, lat, lng) in spots.items():
            worker = User.objects.get(pk=self.users[name].pk)
            if not Ticket.objects.filter(assigned_to=worker, status=S.IN_PROGRESS).exists():
                worker.current_location = self.locations[loc_key]
            worker.last_lat, worker.last_lng = Decimal(str(lat)), Decimal(str(lng))
            worker.location_updated_at = self.base_now - timedelta(minutes=rng.randint(5, 90))
            worker.save()

        # Older notifications are already handled; keep the inbox realistic
        Reminder.objects.filter(due_at__lt=self.base_now - timedelta(hours=12)).update(
            is_done=True, done_at=self.base_now
        )
        self._set_time(self.base_now)
        services.notify(
            self.users["student_demo"], "Check whether the room fan works after tonight's repair.",
            kind=Reminder.Kind.MANUAL, created_by=self.users["student_demo"],
            due_at=self.base_now + timedelta(hours=5),
        )
        self.stdout.write(f"  Created {count} sample complaints.")

    def _advance(self, ticket, final, created, admin, worker, requester):
        rng = self.rng
        when = created

        def step(to, actor, hours, data=None):
            nonlocal ticket, when
            when = when + timedelta(hours=hours)
            if when >= self.base_now:
                return False
            self._set_time(when)
            ticket = workflow.perform_transition(ticket, actor, to, data or {})
            return True

        if final == S.SUBMITTED:
            return
        if final == S.REJECTED:
            step(S.REJECTED, admin, rng.uniform(1, 5), {"reason": "Duplicate of an existing request."})
            return
        if final == S.CANCELLED:
            step(S.CANCELLED, requester, rng.uniform(0.5, 3), {"reason": "Resolved on its own."})
            return
        if not step(S.TRIAGED, admin, rng.uniform(0.2, 1.5)) or final == S.TRIAGED:
            return
        if not step(S.ASSIGNED, admin, rng.uniform(0.3, 2), {"assignee": worker}) or final == S.ASSIGNED:
            return
        if not step(S.IN_PROGRESS, worker, rng.uniform(0.5, 4)) or final == S.IN_PROGRESS:
            return
        if final == S.WAITING_PARTS or rng.random() < 0.15:
            if not step(S.WAITING_PARTS, worker, rng.uniform(0.5, 2),
                        {"reason": "Spare part ordered from the store."}):
                return
            if final == S.WAITING_PARTS:
                return
            if not step(S.IN_PROGRESS, worker, rng.uniform(6, 30)):
                return
        cost = rng.choice(["0", "0", "0", "120", "180", "350"])
        if not step(S.REPORTED_FIXED, worker, rng.uniform(0.5, 6), {
            "checklist": True, "work_notes": "Repaired and tested.", "material_cost": cost,
        }) or final == S.REPORTED_FIXED:
            return
        if final == S.CLOSED_UNVERIFIED:
            step(S.CLOSED_UNVERIFIED, None, 73)
            return
        if rng.random() < 0.3:
            ok = step(S.VERIFIED_FIXED, worker, 0.1, {"code": ticket.completion_code})
        else:
            ok = step(S.VERIFIED_FIXED, requester, rng.uniform(0.5, 20))
        if ok and when < self.base_now - timedelta(days=5):
            payment = WorkerPayment.objects.filter(ticket=ticket).first()
            if payment:
                self._set_time(when + timedelta(days=2))
                mark_paid(payment, method=rng.choice(["upi", "upi", "bank", "cash"]),
                          reference=f"UPI{rng.randint(100000, 999999)}")
