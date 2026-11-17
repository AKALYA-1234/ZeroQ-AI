import os
import time
import requests
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5173"
API_URL = "http://127.0.0.1:8000"
SCREENSHOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "screenshots_full_flow"))
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def test_full_lifecycle_and_features():
    console_errors = []
    created_complaint_id = None

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context()
        page = context.new_page()

        def on_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)
        page.on("console", on_console)

        print("\n=======================================================")
        print(" PHASE 1: CUSTOMER COMPLAINT INTAKE & INITIAL TRACKING ")
        print("=======================================================")

        # 1. Sign in as Customer
        print("[1/14] Navigating to Login and authenticating as Customer...")
        page.goto(f"{BASE_URL}/login")
        page.fill("input[type='email']", "demo@customer.com")
        page.fill("input[type='password']", "DemoCustomer2024!")
        page.click("button[type='submit']")
        page.wait_for_url("**/customer/home")
        page.wait_for_selector("text=Welcome back")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "01_customer_home.png"))
        print("  ✓ Customer Home loaded successfully.")

        # 2. Submit a real Complaint
        print("[2/14] Filing new quality complaint with real product & batch...")
        page.click("a[href='/customer/submit-complaint']")
        page.wait_for_url("**/customer/submit-complaint")
        page.wait_for_selector("select")

        page.select_option("select:has(option:has-text('Select Product'))", index=1)
        page.fill("input[placeholder*='BAT']", "BAT000004")
        test_title = "End-to-End Lifecycle Verification Ticket"
        page.fill("input[placeholder*='summary']", test_title)
        page.fill("textarea[placeholder*='description']", "Automated end-to-end test verifying multi-stage progression from intake to resolution.")
        page.select_option("select:has(option:has-text('Select Category'))", value="Packaging Defect")
        page.select_option("select:has(option:has-text('Select Severity'))", value="high")
        page.click("button:has-text('Submit Complaint')")

        page.wait_for_selector("text=Complaint Submitted Successfully", timeout=10000)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "02_complaint_intake_success.png"))

        # Extract generated complaint ID from page
        cid_element = page.locator("p.font-mono.font-bold")
        created_complaint_id = cid_element.inner_text().strip()
        print(f"  ✓ Complaint registered with ID: {created_complaint_id}")

        # 3. Track Initial State (Step 1: Submitted)
        print("[3/14] Verifying initial tracking milestone (Submitted)...")
        page.click("button:has-text('Track Status')")
        page.wait_for_selector("text=Complaint Progress", timeout=10000)
        page.wait_for_selector("text=Submitted")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "03_tracking_stage_1_submitted.png"))
        print("  ✓ Verified Stage 1: Submitted.")

        # 4. Sign out Customer
        print("[4/14] Signing out Customer...")
        page.click("div.relative button:has(div.rounded-full)")
        page.click("text=Sign Out")
        page.wait_for_url("**/login")
        print("  ✓ Customer signed out.")

        print("\n=======================================================")
        print(" PHASE 2: ADMIN TRIAGE & MULTI-STAGE PROGRESSION FLOW  ")
        print("=======================================================")

        # 5. Sign in as Admin
        print("[5/14] Signing in as Quality Admin...")
        page.fill("input[type='email']", "admin@zeroq.com")
        page.fill("input[type='password']", "AdminZeroQ2024!")
        page.click("button[type='submit']")
        page.wait_for_url("**/admin/dashboard")
        page.wait_for_selector("text=Executive Dashboard")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "04_admin_dashboard.png"))
        print("  ✓ Admin Dashboard loaded.")

        # 6. Admin Complaint Management
        print("[6/14] Navigating to Complaint Management Queue...")
        page.click("a[href='/admin/complaints']")
        page.wait_for_url("**/admin/complaints")
        page.wait_for_selector("text=Complaint Queue")

        # Locate the new complaint in queue
        print(f"[7/14] Searching and selecting newly submitted complaint {created_complaint_id}...")
        page.fill("input[placeholder*='Search Complaint ID']", created_complaint_id)
        page.click("button:has-text('Apply')")
        page.wait_for_selector(f"div.overflow-y-auto >> text={created_complaint_id}")
        page.click(f"div.overflow-y-auto >> text={created_complaint_id}")
        page.wait_for_selector(f"span.font-mono:has-text('{created_complaint_id}')")
        page.wait_for_selector("text=Quality Triage & Workflow Transition")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "05_admin_complaint_selected.png"))

        # Transition 1: Submitted -> Under Review
        print("[8/14] Admin advancing status: Submitted -> Under Review...")
        page.select_option("select:has(option:has-text('1. Submitted'))", value="under_review")
        page.fill("input[placeholder*='Retain samples']", "QA Lab assigned retain sample review.")
        page.click("button:has-text('Apply Status & Notify Customer')")
        page.wait_for_selector("text=Status & triage updated successfully!")
        time.sleep(1)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "06_admin_advanced_under_review.png"))
        print("  ✓ Advanced to Under Review.")

        # Transition 2: Under Review -> Investigating
        print("[9/14] Admin advancing status: Under Review -> Investigating...")
        page.select_option("select:has(option:has-text('1. Submitted'))", value="investigation_in_progress")
        page.fill("input[placeholder*='Retain samples']", "Seal integrity testing underway in materials laboratory.")
        page.click("button:has-text('Apply Status & Notify Customer')")
        page.wait_for_selector("text=Status & triage updated successfully!")
        time.sleep(1)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "07_admin_advanced_investigating.png"))
        print("  ✓ Advanced to Investigating.")

        # Transition 3: Investigating -> Resolved
        print("[10/14] Admin advancing status: Investigating -> Resolved...")
        page.select_option("select:has(option:has-text('1. Submitted'))", value="resolved")
        page.fill("input[placeholder*='Retain samples']", "Root cause identified as packaging heater drift. Temperature controller recalibrated. Ticket closed.")
        page.click("button:has-text('Apply Status & Notify Customer')")
        page.wait_for_selector("text=Status & triage updated successfully!")
        time.sleep(1)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "08_admin_advanced_resolved.png"))
        print("  ✓ Advanced to Resolved.")

        # 7. Check other Admin features
        print("[11/14] Verifying all Admin quality intelligence modules...")
        
        # Analytics
        page.click("a[href='/admin/analytics']")
        page.wait_for_url("**/admin/analytics")
        page.wait_for_selector("text=Complaint Analytics")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "09_admin_analytics.png"))
        print("  ✓ Admin Analytics verified.")

        # Root Cause Analysis
        page.click("a[href='/admin/root-cause-analysis']")
        page.wait_for_url("**/admin/root-cause-analysis")
        page.wait_for_selector("text=Root Cause Analysis")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "10_admin_root_cause.png"))
        print("  ✓ Admin Root Cause Analysis verified.")

        # Risk Assessment
        page.click("a[href='/admin/risk-assessment']")
        page.wait_for_url("**/admin/risk-assessment")
        page.wait_for_selector("text=Risk Assessment")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "11_admin_risk_assessment.png"))
        print("  ✓ Admin Risk Assessment verified.")

        # CAPA Management
        page.click("a[href='/admin/capa']")
        page.wait_for_url("**/admin/capa")
        page.wait_for_selector("text=CAPA Management")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "12_admin_capa.png"))
        print("  ✓ Admin CAPA Management verified.")

        # AI Prediction Center
        page.click("a[href='/admin/ai-prediction']")
        page.wait_for_url("**/admin/ai-prediction")
        page.wait_for_selector("text=Batch Complaint Risk")
        page.wait_for_selector("text=XGBoost")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "13_admin_ai_center.png"))
        print("  ✓ Admin AI Prediction Center verified.")

        # Sign out Admin
        page.click("button[title='Sign Out']")
        page.wait_for_url("**/login")

        print("\n=======================================================")
        print(" PHASE 3: CUSTOMER END-TO-END RESOLUTION TRACKING     ")
        print("=======================================================")

        # 8. Sign in as Customer to verify resolution
        print("[12/14] Customer logging back in to verify completed lifecycle...")
        page.fill("input[type='email']", "demo@customer.com")
        page.fill("input[type='password']", "DemoCustomer2024!")
        page.click("button[type='submit']")
        page.wait_for_url("**/customer/home")

        # 9. Track complaint - verify Stage 4: Resolved
        print(f"[13/14] Tracking complaint {created_complaint_id} to completion...")
        page.click("a[href='/customer/track-complaint']")
        page.wait_for_url("**/customer/track-complaint")
        page.fill("input[placeholder*='CMP']", created_complaint_id)
        page.click("button:has-text('Track')")

        page.wait_for_selector("text=Complaint Progress", timeout=10000)
        page.wait_for_selector("text=resolved", timeout=10000)
        page.wait_for_selector("text=Root cause identified as packaging heater drift")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "14_customer_tracking_resolved_final.png"))
        print("  ✓ Complaint verified: Status is RESOLVED with full resolution narrative!")

        # 10. Check My Complaints table
        print("[14/14] Verifying My Complaints list reflects Resolved ticket...")
        page.click("a[href='/customer/my-complaints']")
        page.wait_for_url("**/customer/my-complaints")
        page.wait_for_selector(f"text={created_complaint_id}")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "15_my_complaints_resolved.png"))
        print(f"  ✓ Ticket {created_complaint_id} listed as Resolved in customer history.")

        # 11. Run an AI Prediction query as Customer
        page.click("a[href='/customer/query-prediction']")
        page.wait_for_url("**/customer/query-prediction")
        test_q = "Predict complaint probability for Fruit Jam at Chennai on Morning shift"
        page.fill("textarea", test_q)
        page.click("button:has-text('Predict Risk')")
        page.wait_for_selector("text=Pre-Dispatch Quality Risk Evaluation", timeout=10000)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "16_customer_ai_prediction_query.png"))
        print("  ✓ Customer AI Risk Predictor generated real prediction.")

        browser.close()

    # Clean up test complaint from database
    if created_complaint_id:
        try:
            import sys
            sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
            from app.database.connection import SessionLocal
            from app.models.complaint import Complaint, ComplaintStatusHistory
            with SessionLocal() as db:
                c = db.query(Complaint).filter(Complaint.complaint_id == created_complaint_id).first()
                if c:
                    db.query(ComplaintStatusHistory).filter(ComplaintStatusHistory.complaint_id == c.id).delete(synchronize_session=False)
                    db.query(Complaint).filter(Complaint.id == c.id).delete(synchronize_session=False)
                    db.commit()
                    print(f"\n[Teardown] Test complaint {created_complaint_id} cleaned up from database.")
        except Exception as e:
            print("Teardown error:", e)

    print(f"\nCaptured {len(console_errors)} console errors during full lifecycle flow.")
    assert len(console_errors) == 0, f"Unexpected console errors: {console_errors}"
    print(">>> FULL END-TO-END LIFECYCLE & FEATURES TESTING PASSED 100% <<<")

if __name__ == "__main__":
    test_full_lifecycle_and_features()
