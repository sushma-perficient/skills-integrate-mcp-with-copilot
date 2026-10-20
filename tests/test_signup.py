from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import unittest

from fastapi import HTTPException

from src import app as app_module


class SignupTests(unittest.TestCase):
    def setUp(self):
        self.original_activities = app_module.activities
        app_module.activities = {
            "Limited Activity": {
                "max_participants": 2,
                "participants": ["existing@mergington.edu"],
            }
        }

    def tearDown(self):
        app_module.activities = self.original_activities

    def test_rejects_signup_when_activity_is_full(self):
        app_module.activities["Limited Activity"]["participants"].append(
            "second@mergington.edu"
        )
        with self.assertRaises(HTTPException) as error:
            app_module.signup_for_activity(
                "Limited Activity", "new@mergington.edu"
            )

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(
            app_module.activities["Limited Activity"]["participants"],
            ["existing@mergington.edu", "second@mergington.edu"],
        )

    def test_rejects_grade_outside_configured_eligibility(self):
        app_module.activities["Limited Activity"]["eligible_grades"] = [10, 11]

        with self.assertRaises(HTTPException) as error:
            app_module.signup_for_activity(
                "Limited Activity", "new@mergington.edu", grade=9
            )

        self.assertEqual(error.exception.status_code, 403)

    def test_accepts_grade_within_configured_eligibility(self):
        app_module.activities["Limited Activity"]["eligible_grades"] = [10, 11]

        result = app_module.signup_for_activity(
            "Limited Activity", "new@mergington.edu", grade=10
        )

        self.assertIn(
            "new@mergington.edu",
            app_module.activities["Limited Activity"]["participants"],
        )
        self.assertEqual(
            result["message"], "Signed up new@mergington.edu for Limited Activity"
        )

    def test_requires_grade_when_activity_has_grade_restrictions(self):
        app_module.activities["Limited Activity"]["eligible_grades"] = [10, 11]

        with self.assertRaises(HTTPException) as error:
            app_module.signup_for_activity(
                "Limited Activity", "new@mergington.edu"
            )

        self.assertEqual(error.exception.status_code, 400)

    def test_rejects_signup_after_deadline(self):
        deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
        app_module.activities["Limited Activity"]["signup_deadline"] = deadline.isoformat()

        with self.assertRaises(HTTPException) as error:
            app_module.signup_for_activity(
                "Limited Activity", "new@mergington.edu"
            )

        self.assertEqual(error.exception.status_code, 409)

    def test_only_one_concurrent_signup_can_take_last_spot(self):
        emails = [f"student{index}@mergington.edu" for index in range(10)]

        def signup(email):
            try:
                app_module.signup_for_activity("Limited Activity", email)
                return True
            except HTTPException:
                return False

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(signup, emails))

        self.assertEqual(sum(results), 1)
        self.assertEqual(len(app_module.activities["Limited Activity"]["participants"]), 2)


if __name__ == "__main__":
    unittest.main()