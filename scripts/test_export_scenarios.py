import os
import sys
import django
from io import BytesIO
import openpyxl

from pathlib import Path
base_dir = Path(__file__).resolve().parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

try:
    import dotenv
    env_path = base_dir / ".env"
    if env_path.exists():
        dotenv.load_dotenv(env_path)
except ImportError:
    pass

# Initialize Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sakthi_erp.settings")
django.setup()

from rest_framework.test import APIRequestFactory, force_authenticate
from api.views.reports_export_views.inventory_history_export import export_inventory_history_excel
from api.models import InventoryHistory, All_User

factory = APIRequestFactory()

DEFAULT_HEADERS = [
    {"field": "sno", "header": "SL.NO"},
    {"field": "created_date", "header": "DATE"},
    {"field": "created_time", "header": "TIME"},
    {"field": "part_name", "header": "ITEM NAME"},
    {"field": "action", "header": "ACTION"},
    {"field": "quantity", "header": "QTY"},
    {"field": "purchase_price", "header": "RATE/QTY"},
    {"field": "machine_name", "header": "MACHINE NAME"},
    {"field": "user", "header": "USER"},
    {"field": "remarks", "header": "REMARKS"},
]

def fetch_all_history_rows():
    qs = InventoryHistory.objects.all().order_by("-id")
    rows = []
    for idx, item in enumerate(qs):
        rows.append({
            "sno": idx + 1,
            "created_date": item.created_at.strftime("%Y-%m-%d") if item.created_at else "-",
            "created_time": item.created_at.strftime("%I:%M %p") if item.created_at else "-",
            "part_name": item.part_name or "-",
            "action": item.action or "-",
            "quantity": float(item.quantity or 0),
            "purchase_price": float(item.purchase_price or 0),
            "machine_name": item.machine_name or "Common Machine",
            "user": item.user or "-",
            "remarks": item.remarks or "-",
        })
    return rows

def test_export_scenarios():
    all_rows = fetch_all_history_rows()
    print("\n" + "=" * 70)
    print(f">> RUNNING 10 EXCEL EXPORT SCENARIOS (Total Base Records: {len(all_rows)})")
    print("=" * 70)

    scenarios = [
        {
            "name": "Scenario 1: Full History Export (All rows, all default columns)",
            "rows": all_rows,
            "headers": DEFAULT_HEADERS,
        },
        {
            "name": "Scenario 2: Filter by Action: 'Added' Only",
            "rows": [r for r in all_rows if "add" in str(r["action"]).lower()],
            "headers": DEFAULT_HEADERS,
        },
        {
            "name": "Scenario 3: Filter by Action: 'Used' Only",
            "rows": [r for r in all_rows if "use" in str(r["action"]).lower()],
            "headers": DEFAULT_HEADERS,
        },
        {
            "name": "Scenario 4: Filter by Action: 'Updated' Only (Restocked)",
            "rows": [r for r in all_rows if "update" in str(r["action"]).lower()],
            "headers": DEFAULT_HEADERS,
        },
        {
            "name": "Scenario 5: Filter by Action: 'Edited' Only (Specification edits)",
            "rows": [r for r in all_rows if "edit" in str(r["action"]).lower()],
            "headers": DEFAULT_HEADERS,
        },
        {
            "name": "Scenario 6: Filter by Action: 'Deleted' Only",
            "rows": [r for r in all_rows if "del" in str(r["action"]).lower()],
            "headers": DEFAULT_HEADERS,
        },
        {
            "name": "Scenario 7: Filter by Machine: 'Bystronic Laser 10kW'",
            "rows": [r for r in all_rows if "bystronic" in str(r["machine_name"]).lower()],
            "headers": DEFAULT_HEADERS,
        },
        {
            "name": "Scenario 8: Filter by User: 'Murugan (Maintenance)'",
            "rows": [r for r in all_rows if "murugan" in str(r["user"]).lower()],
            "headers": DEFAULT_HEADERS,
        },
        {
            "name": "Scenario 9: Checkbox Selection (Selective 5 specific rows)",
            "rows": all_rows[:5],
            "headers": DEFAULT_HEADERS,
        },
        {
            "name": "Scenario 10: Custom Selected Columns (Item, Action, Qty, Rate, Machine)",
            "rows": all_rows[:15],
            "headers": [
                {"field": "sno", "header": "SL.NO"},
                {"field": "part_name", "header": "ITEM NAME"},
                {"field": "action", "header": "ACTION"},
                {"field": "quantity", "header": "QTY"},
                {"field": "purchase_price", "header": "RATE/QTY"},
                {"field": "machine_name", "header": "MACHINE NAME"},
            ],
        },
        {
            "name": "Scenario 11: Single Row Export (Totals row MUST NOT be present)",
            "rows": all_rows[:1],
            "headers": DEFAULT_HEADERS,
            "expect_no_totals": True,
        },
    ]

    test_user, _ = All_User.objects.get_or_create(
        username="admin_tester",
        defaults={"email": "admin@sakthi.com", "isAdmin": True, "password": "pass"}
    )

    passed_count = 0

    for i, sc in enumerate(scenarios, 1):
        payload = {
            "headers": sc["headers"],
            "rows": sc["rows"],
        }
        request = factory.post("/api/export_inventory_history_excel/", payload, format="json")
        force_authenticate(request, user=test_user)
        response = export_inventory_history_excel(request)

        # Validations
        if response.status_code != 200:
            print(f"[FAIL] {sc['name']}: HTTP status {response.status_code}")
            continue

        if not response.has_header("Content-Disposition"):
            print(f"[FAIL] {sc['name']}: Missing Content-Disposition header")
            continue

        file_bytes = response.content
        if len(file_bytes) < 1000:
            print(f"[FAIL] {sc['name']}: Output size too small ({len(file_bytes)} bytes)")
            continue

        # Load workbook with openpyxl to verify sheet validity and data
        wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=False)
        sheet = wb.active

        # Count data rows (header is row 4, data starts at row 5)
        total_rows_in_sheet = sheet.max_row
        header_row_values = [cell.value for cell in sheet[4] if cell.value]

        if sc.get("expect_no_totals") and total_rows_in_sheet > 6:
            print(f"[FAIL] {sc['name']}: Total rows found when expecting none (Sheet max_row: {total_rows_in_sheet})")
            continue

        print(f"[{i:02d}/{len(scenarios)}] [PASS] {sc['name']}")
        print(f"       -> Input Rows: {len(sc['rows'])} | Sheet Rows: {total_rows_in_sheet} | File Size: {len(file_bytes):,} bytes | Headers: {len(header_row_values)}")
        passed_count += 1

    print("=" * 70)
    print(f"SUMMARY: {passed_count}/{len(scenarios)} SCENARIOS PASSED")
    print("=" * 70 + "\n")
    return passed_count == len(scenarios)

if __name__ == "__main__":
    success = test_export_scenarios()
    if not success:
        sys.exit(1)
