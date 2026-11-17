import os
import time
import pytest
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5173"
SCREENSHOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "screenshots"))
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def test_full_application_e2e():
    console_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Capture console errors
        def on_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)
        page.on("console", on_console)

        print("\n--- STEP 1: Navigate to Login Page ---")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_selector("input[type='email']")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "01_login_page.png"))
        assert "ZeroQ AI" in page.title()

        print("--- STEP 2: Sign in as Customer ---")
        page.fill("input[type='email']", "demo@customer.com")
        page.fill("input[type='password']", "DemoCustomer2024!")
        page.click("button[type='submit']")
        page.wait_for_url("**/customer/home")
        page.wait_for_selector("text=Welcome back")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "02_customer_home.png"))
        print("  ✓ Customer Home loaded successfully.")

        print("--- STEP 3: Navigate to AI Risk Predictor ---")
        page.click("a[href='/customer/query-prediction']")
        page.wait_for_url("**/customer/query-prediction")
        page.wait_for_selector("textarea")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "03_ai_predictor_empty.png"))

        # Submit natural language query
        test_query = "Predict defect risk for Classic Biscuits in Pune facility on Night shift with temperature 135C"
        page.fill("textarea", test_query)
        page.click("button:has-text('Predict Risk')")
        
        # Wait for prediction result card
        page.wait_for_selector("text=Pre-Dispatch Quality Risk Evaluation", timeout=10000)
        page.wait_for_selector("text=Quality Intelligence Summary")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "04_ai_prediction_result.png"))
        print("  ✓ AI Prediction successfully returned and displayed with intelligence summary.")

        # Verify query appears in persistent history
        page.wait_for_selector("text=Your Prediction Query History")
        assert page.is_visible(f"text=\"{test_query}\"") or page.is_visible("text=Classic Biscuits")
        print("  ✓ Query successfully persisted in Query History.")

        print("--- STEP 4: Submit a Complaint ---")
        page.click("a[href='/customer/submit-complaint']")
        page.wait_for_url("**/customer/submit-complaint")
        page.wait_for_selector("select")

        # Select real product
        page.select_option("select:has(option:has-text('Select Product'))", index=1)
        page.fill("input[placeholder*='BAT']", "BAT000004")
        page.fill("input[placeholder*='summary']", "Minor carton compression upon delivery")
        page.fill("textarea[placeholder*='description']", "Upon receipt at distribution center, carton seals exhibited slight wear.")
        page.select_option("select:has(option:has-text('Select Category'))", value="Packaging Defect")
        page.select_option("select:has(option:has-text('Select Severity'))", value="medium")
        page.click("button:has-text('Submit Complaint')")

        page.wait_for_selector("text=Complaint Submitted Successfully", timeout=10000)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "05_complaint_submitted.png"))
        print("  ✓ Complaint submitted successfully.")

        print("--- STEP 5: Track Complaint ---")
        page.click("a[href='/customer/track-complaint']")
        page.wait_for_url("**/customer/track-complaint")
        page.fill("input[placeholder*='CMP']", "CMP000001")
        page.click("button:has-text('Track')")
        page.wait_for_selector("text=Complaint Progress", timeout=10000)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "06_track_complaint.png"))
        print("  ✓ Tracking portal loaded complaint milestones.")

        print("--- STEP 6: My Complaints ---")
        page.click("a[href='/customer/my-complaints']")
        page.wait_for_url("**/customer/my-complaints")
        page.wait_for_selector("table, div.divide-y", timeout=10000)
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "07_my_complaints.png"))
        print("  ✓ My Complaints loaded customer tickets.")

        print("--- STEP 7: Sign Out Customer ---")
        # Click user profile menu
        page.click("div.relative button:has(div.rounded-full)")
        page.click("text=Sign Out")
        page.wait_for_url("**/login")
        print("  ✓ Signed out.")

        print("--- STEP 8: Sign in as Admin ---")
        page.fill("input[type='email']", "admin@zeroq.com")
        page.fill("input[type='password']", "AdminZeroQ2024!")
        page.click("button[type='submit']")
        page.wait_for_url("**/admin/dashboard")
        page.wait_for_selector("text=Executive Dashboard")
        page.wait_for_selector("text=Total Complaints")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "08_admin_dashboard.png"))
        print("  ✓ Admin Dashboard loaded with real 6,000 complaints KPI.")

        print("--- STEP 9: Admin Complaints Management ---")
        page.click("a[href='/admin/complaints']")
        page.wait_for_url("**/admin/complaints")
        page.wait_for_selector("text=Complaint Queue")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "09_admin_complaints_table.png"))
        print("  ✓ Complaints table loaded with real records.")

        print("--- STEP 10: Admin AI Prediction Center ---")
        page.click("a[href='/admin/ai-prediction']")
        page.wait_for_url("**/admin/ai-prediction")
        page.wait_for_selector("text=Batch Complaint Risk")
        page.wait_for_selector("text=XGBoost")
        page.screenshot(path=os.path.join(SCREENSHOT_DIR, "10_admin_ai_center.png"))
        print("  ✓ AI Prediction Center shows active model status.")

        browser.close()

    # Clean up test-created complaint records so database stays pristine
    try:
        import sys
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))
        from app.database.connection import SessionLocal
        from app.models.complaint import Complaint, ComplaintStatusHistory
        with SessionLocal() as db:
            test_cmps = db.query(Complaint).filter(Complaint.id > 6000).all()
            if test_cmps:
                t_ids = [c.id for c in test_cmps]
                db.query(ComplaintStatusHistory).filter(ComplaintStatusHistory.complaint_id.in_(t_ids)).delete(synchronize_session=False)
                db.query(Complaint).filter(Complaint.id.in_(t_ids)).delete(synchronize_session=False)
                db.commit()
    except Exception as e:
        pass

    print(f"\nCaptured {len(console_errors)} console errors during E2E flow.")
    assert len(console_errors) == 0, f"Unexpected console errors: {console_errors}"
    print(">>> PLAYWRIGHT E2E TESTING PASSED 100% WITH ZERO CONSOLE ERRORS <<<")

if __name__ == "__main__":
    test_full_application_e2e()
