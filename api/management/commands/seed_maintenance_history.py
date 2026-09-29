import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from api.models import Machine, MaintenanceSchedule, MachineMaintenanceLog, BreakdownMaintenance


class Command(BaseCommand):
    help = "Seeds database with at least 10 Periodic and 10 Breakdown maintenance records for testing"

    def handle(self, *args, **options):
        self.stdout.write("Seeding maintenance history test records...")
        today = timezone.now().date()

        # 1. Create or get standard test machines
        machines_data = [
            ("TRUMPF TruLaser 3030", True),
            ("AMADA Press Brake 100T", False),
            ("Hydraulic Shearing 12mm", False),
            ("Fiber Laser Cutter 4kW", True),
            ("Mazak CNC Lathe QT-250", False),
            ("Haas 3-Axis VMC Milling", False),
            ("Fanuc Robotic Welding Cell", True),
            ("Kaeser Screw Compressor 50HP", False),
            ("Atlas Copco Nitrogen Gen", True),
            ("Omax Waterjet 55100", False),
        ]

        machines = {}
        for name, needs_gas in machines_data:
            m, _ = Machine.objects.get_or_create(
                machine_name=name,
                defaults={"does_need_gas": needs_gas, "created_by": "SYSTEM_SEED"},
            )
            machines[name] = m

        # 2. Seed 10+ Periodic Maintenance Schedules & Logs
        periodic_configs = [
            {
                "machine": machines["TRUMPF TruLaser 3030"],
                "name": "Optical Lens Cleaning & Calibration",
                "needs": "Clean focus lens with pure IPA and calibrate laser beam center",
                "interval": 14,
                "last_date": today - datetime.timedelta(days=20),
                "next_date": today - datetime.timedelta(days=6),  # Overdue
                "status": "active",
                "created_by": "ADMIN",
            },
            {
                "machine": machines["AMADA Press Brake 100T"],
                "name": "Hydraulic Proportional Valve & Oil Filter Check",
                "needs": "Inspect valve response time and change return line filter",
                "interval": 30,
                "last_date": today - datetime.timedelta(days=30),
                "next_date": today,  # Due today
                "status": "active",
                "created_by": "MAINT_SUPERVISOR",
            },
            {
                "machine": machines["Hydraulic Shearing 12mm"],
                "name": "Shear Blade Clearance & Gap Adjustment",
                "needs": "Verify blade tolerance gap with feeler gauge (0.15mm target)",
                "interval": 45,
                "last_date": today - datetime.timedelta(days=44),
                "next_date": today + datetime.timedelta(days=1),  # Due tomorrow
                "status": "active",
                "created_by": "ADMIN",
            },
            {
                "machine": machines["Fiber Laser Cutter 4kW"],
                "name": "Water Chiller Flush & Coolant Conductivity Test",
                "needs": "Deionize water tank, replace filter cartridge, check flow rate >40L/min",
                "interval": 60,
                "last_date": today - datetime.timedelta(days=56),
                "next_date": today + datetime.timedelta(days=4),  # Upcoming
                "status": "active",
                "created_by": "TECH_LEAD",
            },
            {
                "machine": machines["Mazak CNC Lathe QT-250"],
                "name": "Spindle Taper Runout & Chuck Clamping Force Check",
                "needs": "Measure dial indicator runout (<0.003mm) and hydraulic clamp psi",
                "interval": 90,
                "last_date": today - datetime.timedelta(days=20),
                "next_date": today + datetime.timedelta(days=70),  # Safe
                "status": "active",
                "created_by": "ADMIN",
            },
            {
                "machine": machines["Haas 3-Axis VMC Milling"],
                "name": "XYZ Linear Guide Lubrication & Ball Screw Backlash",
                "needs": "Pump Mobil Vactra #2 into way lube ports and measure backlash",
                "interval": 30,
                "last_date": today - datetime.timedelta(days=10),
                "next_date": today + datetime.timedelta(days=20),  # Safe
                "status": "active",
                "created_by": "MAINT_TECH",
            },
            {
                "machine": machines["Fanuc Robotic Welding Cell"],
                "name": "Welding Torch Liner & Contact Tip Inspection",
                "needs": "Replace worn contact tips, blow out spiral liner, clean gas shroud",
                "interval": 7,
                "last_date": today - datetime.timedelta(days=12),
                "next_date": today - datetime.timedelta(days=5),  # Overdue
                "status": "active",
                "created_by": "ROBOTICS_ENG",
            },
            {
                "machine": machines["Kaeser Screw Compressor 50HP"],
                "name": "Air Intake Filter & Oil Separator Element Replacement",
                "needs": "Replace 5-micron air filter and check compressor oil differential pressure",
                "interval": 120,
                "last_date": today - datetime.timedelta(days=40),
                "next_date": today + datetime.timedelta(days=80),  # Safe
                "status": "active",
                "created_by": "ADMIN",
            },
            {
                "machine": machines["Atlas Copco Nitrogen Gen"],
                "name": "CMS Carbon Molecular Sieve Purity & Oxygen Sensor Test",
                "needs": "Calibrate zirconia O2 sensor and verify 99.999% N2 output purity",
                "interval": 180,
                "last_date": today - datetime.timedelta(days=30),
                "next_date": today + datetime.timedelta(days=150),  # Safe
                "status": "active",
                "created_by": "GAS_TECH",
            },
            {
                "machine": machines["Omax Waterjet 55100"],
                "name": "High-Pressure Seal & Diamond Orifice Overhaul",
                "needs": "Overhaul 60,000 PSI intensifier check valves and diamond orifice assembly",
                "interval": 365,
                "last_date": today - datetime.timedelta(days=100),
                "next_date": today + datetime.timedelta(days=265),  # Safe
                "status": "active",
                "created_by": "ADMIN",
            },
        ]

        created_scheds = []
        for p in periodic_configs:
            sched, _ = MaintenanceSchedule.objects.update_or_create(
                machine=p["machine"],
                maintenance_name=p["name"],
                defaults={
                    "maintenance_needs": p["needs"],
                    "interval_days": p["interval"],
                    "last_maintenance_date": p["last_date"],
                    "next_maintenance_date": p["next_date"],
                    "status": p["status"],
                    "created_by": p["created_by"],
                },
            )
            created_scheds.append(sched)

        # Also add 3 completed historical maintenance logs for periodic maintenance
        logs_data = [
            (
                machines["TRUMPF TruLaser 3030"],
                created_scheds[0],
                "Optical Lens Cleaning & Calibration",
                today - datetime.timedelta(days=20),
                today - datetime.timedelta(days=20),
                "Focus Lens D28mm x1, Lens Tissue x5",
                "ADMIN",
            ),
            (
                machines["AMADA Press Brake 100T"],
                created_scheds[1],
                "Hydraulic Proportional Valve & Oil Filter Check",
                today - datetime.timedelta(days=30),
                today - datetime.timedelta(days=30),
                "Hydraulic Filter Cartridge HC9000 x2, Mobil DTE 24 Oil 20L",
                "MAINT_SUPERVISOR",
            ),
            (
                machines["Fanuc Robotic Welding Cell"],
                created_scheds[6],
                "Welding Torch Liner & Contact Tip Inspection",
                today - datetime.timedelta(days=12),
                today - datetime.timedelta(days=12),
                "Contact Tip 1.2mm CuCrZr x5, Gas Diffuser x2",
                "ROBOTICS_ENG",
            ),
        ]

        for m, sched, name, s_date, a_date, parts, approved_by in logs_data:
            MachineMaintenanceLog.objects.get_or_create(
                machine=m,
                schedule=sched,
                maintenance_name=name,
                scheduled_date=s_date,
                defaults={
                    "approved_date": a_date,
                    "status": "approved",
                    "approved_by": approved_by,
                    "parts_used": parts,
                },
            )

        # 3. Seed 10+ Breakdown Maintenance Records
        breakdown_records = [
            {
                "record_number": "BM-1001",
                "machine": machines["TRUMPF TruLaser 3030"],
                "breakdown_date": today - datetime.timedelta(days=25),
                "shift": "Shift 1",
                "affected_equipment": "Laser Cutting Head",
                "operator_name": "Ramesh Kumar",
                "supervisor": "Admin",
                "breakdown_type": "Protective Glass Thermal Breakdown",
                "breakdown_time": datetime.time(9, 15),
                "maintenance_start_time": datetime.time(9, 30),
                "maintenance_complete_time": datetime.time(10, 15),
                "restart_time": datetime.time(10, 15),
                "breakdown_complete_date": today - datetime.timedelta(days=25),
                "total_downtime_hours": 1.0,
                "created_by": "OPERATOR_1",
            },
            {
                "record_number": "BM-1002",
                "machine": machines["AMADA Press Brake 100T"],
                "breakdown_date": today - datetime.timedelta(days=22),
                "shift": "Shift 2",
                "affected_equipment": "Hydraulic Proportional Valve",
                "operator_name": "Suresh Patel",
                "supervisor": "Maint Head",
                "breakdown_type": "Hydraulic Pressure Fluctuation",
                "breakdown_time": datetime.time(14, 0),
                "maintenance_start_time": datetime.time(14, 15),
                "maintenance_complete_time": datetime.time(16, 45),
                "restart_time": datetime.time(16, 45),
                "breakdown_complete_date": today - datetime.timedelta(days=22),
                "total_downtime_hours": 2.75,
                "created_by": "OPERATOR_2",
            },
            {
                "record_number": "BM-1003",
                "machine": machines["Hydraulic Shearing 12mm"],
                "breakdown_date": today - datetime.timedelta(days=18),
                "shift": "Shift 1",
                "affected_equipment": "Hold-Down Clamping Cylinder",
                "operator_name": "Vignesh M",
                "supervisor": "Admin",
                "breakdown_type": "Piston Seal Oil Leakage",
                "breakdown_time": datetime.time(8, 30),
                "maintenance_start_time": datetime.time(8, 45),
                "maintenance_complete_time": datetime.time(12, 15),
                "restart_time": datetime.time(12, 15),
                "breakdown_complete_date": today - datetime.timedelta(days=18),
                "total_downtime_hours": 3.75,
                "created_by": "OPERATOR_1",
            },
            {
                "record_number": "BM-1004",
                "machine": machines["Fiber Laser Cutter 4kW"],
                "breakdown_date": today - datetime.timedelta(days=15),
                "shift": "Shift 3",
                "affected_equipment": "Water Chiller Unit",
                "operator_name": "Arunkumar K",
                "supervisor": "Tech Lead",
                "breakdown_type": "High Water Temperature Alarm E-04",
                "breakdown_time": datetime.time(22, 10),
                "maintenance_start_time": datetime.time(22, 30),
                "maintenance_complete_time": datetime.time(23, 15),
                "restart_time": datetime.time(23, 15),
                "breakdown_complete_date": today - datetime.timedelta(days=15),
                "total_downtime_hours": 1.25,
                "created_by": "OPERATOR_3",
            },
            {
                "record_number": "BM-1005",
                "machine": machines["Mazak CNC Lathe QT-250"],
                "breakdown_date": today - datetime.timedelta(days=12),
                "shift": "Shift 2",
                "affected_equipment": "Turret Tool Indexer",
                "operator_name": "Karthik S",
                "supervisor": "Admin",
                "breakdown_type": "Turret Unclamp Sensor Fault",
                "breakdown_time": datetime.time(15, 20),
                "maintenance_start_time": datetime.time(15, 40),
                "maintenance_complete_time": datetime.time(16, 10),
                "restart_time": datetime.time(16, 10),
                "breakdown_complete_date": today - datetime.timedelta(days=12),
                "total_downtime_hours": 0.75,
                "created_by": "OPERATOR_2",
            },
            {
                "record_number": "BM-1006",
                "machine": machines["Haas 3-Axis VMC Milling"],
                "breakdown_date": today - datetime.timedelta(days=9),
                "shift": "Shift 1",
                "affected_equipment": "Spindle Drive Inverter",
                "operator_name": "Prakash R",
                "supervisor": "Maint Head",
                "breakdown_type": "Overcurrent Fault Code 102",
                "breakdown_time": datetime.time(10, 0),
                "maintenance_start_time": datetime.time(10, 30),
                "maintenance_complete_time": datetime.time(14, 30),
                "restart_time": datetime.time(14, 30),
                "breakdown_complete_date": today - datetime.timedelta(days=9),
                "total_downtime_hours": 4.5,
                "created_by": "OPERATOR_1",
            },
            {
                "record_number": "BM-1007",
                "machine": machines["Fanuc Robotic Welding Cell"],
                "breakdown_date": today - datetime.timedelta(days=7),
                "shift": "Shift 2",
                "affected_equipment": "Wire Feeder Drive Motor",
                "operator_name": "Rajesh V",
                "supervisor": "Admin",
                "breakdown_type": "Wire Feed Roller Slippage & Jam",
                "breakdown_time": datetime.time(16, 0),
                "maintenance_start_time": datetime.time(16, 15),
                "maintenance_complete_time": datetime.time(16, 45),
                "restart_time": datetime.time(16, 45),
                "breakdown_complete_date": today - datetime.timedelta(days=7),
                "total_downtime_hours": 0.75,
                "created_by": "OPERATOR_2",
            },
            {
                "record_number": "BM-1008",
                "machine": machines["Kaeser Screw Compressor 50HP"],
                "breakdown_date": today - datetime.timedelta(days=4),
                "shift": "Shift 1",
                "affected_equipment": "V-Belt Drive Assembly",
                "operator_name": "Deepak N",
                "supervisor": "Admin",
                "breakdown_type": "Belt Snapping & High Temp Trip",
                "breakdown_time": datetime.time(11, 0),
                "maintenance_start_time": datetime.time(11, 30),
                "maintenance_complete_time": datetime.time(13, 0),
                "restart_time": datetime.time(13, 0),
                "breakdown_complete_date": today - datetime.timedelta(days=4),
                "total_downtime_hours": 2.0,
                "created_by": "OPERATOR_1",
            },
            {
                "record_number": "BM-1009",
                "machine": machines["Atlas Copco Nitrogen Gen"],
                "breakdown_date": today - datetime.timedelta(days=2),
                "shift": "Shift 3",
                "affected_equipment": "Pneumatic Angle Seat Valve",
                "operator_name": "Manikandan G",
                "supervisor": "Tech Lead",
                "breakdown_type": "Valve Actuator Pilot Air Failure",
                "breakdown_time": datetime.time(23, 0),
                "maintenance_start_time": datetime.time(23, 20),
                "maintenance_complete_time": None,
                "restart_time": None,
                "breakdown_complete_date": None,  # OPEN
                "total_downtime_hours": 5.5,
                "created_by": "OPERATOR_3",
            },
            {
                "record_number": "BM-1010",
                "machine": machines["Omax Waterjet 55100"],
                "breakdown_date": today,
                "shift": "Shift 1",
                "affected_equipment": "Intensifier Pump Check Valve",
                "operator_name": "Anbuchelvan T",
                "supervisor": "Admin",
                "breakdown_type": "High Pressure Water Leakage at Poppet",
                "breakdown_time": datetime.time(7, 45),
                "maintenance_start_time": datetime.time(8, 0),
                "maintenance_complete_time": None,
                "restart_time": None,
                "breakdown_complete_date": None,  # OPEN
                "total_downtime_hours": 3.0,
                "created_by": "OPERATOR_1",
            },
        ]

        for bm in breakdown_records:
            BreakdownMaintenance.objects.update_or_create(
                record_number=bm["record_number"],
                defaults=bm,
            )

        total_periodic = MaintenanceSchedule.objects.count() + MachineMaintenanceLog.objects.count()
        total_breakdown = BreakdownMaintenance.objects.count()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded: {total_periodic} Periodic records ({MaintenanceSchedule.objects.count()} schedules, {MachineMaintenanceLog.objects.count()} logs) "
                f"and {total_breakdown} Breakdown records."
            )
        )
