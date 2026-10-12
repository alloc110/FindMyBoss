from pathlib import Path
import unittest
from starlette.testclient import TestClient

from web.app import app


class TestWebAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_stats_endpoint(self):
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_jobs", data)
        self.assertIn("total_cvs", data)
        self.assertIn("has_gemini_key", data)

    def test_list_jobs_endpoint(self):
        response = self.client.get("/api/jobs?limit=5")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("jobs", data)
        self.assertIn("total", data)
        self.assertIn("page", data)
        self.assertIn("total_pages", data)

    def test_get_profile_and_update(self):
        get_res = self.client.get("/api/profile")
        self.assertEqual(get_res.status_code, 200)
        profile = get_res.json()
        self.assertIn("name", profile)

        # Update profile
        profile["location"] = "Hồ Chí Minh, Việt Nam"
        put_res = self.client.put("/api/profile", json=profile)
        self.assertEqual(put_res.status_code, 200)
        self.assertTrue(put_res.json()["success"])

    def test_serve_html_dashboard(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("FindMyBoss", res.text)
        self.assertIn("ATS Studio", res.text)


    def test_upload_master_cv_pdf(self):
        pdf_path = Path("data/cvs/test_cv.pdf")
        if not pdf_path.exists() or len(pdf_path.read_bytes()) < 100:
            import io, pypdf
            raw_pdf = (
                b"%PDF-1.4\n"
                b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
                b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
                b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
                b"5 0 obj<</Length 44>>stream\n"
                b"BT /F1 12 Tf 100 700 Td (Hello World Master CV) Tj ET\n"
                b"endstream\n"
                b"endobj\n"
                b"xref\n0 6\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000102 00000 n\n0000000213 00000 n\n0000000279 00000 n\n"
                b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n374\n%%EOF\n"
            )
            r = pypdf.PdfReader(io.BytesIO(raw_pdf))
            w = pypdf.PdfWriter()
            w.append(r)
            buf = io.BytesIO()
            w.write(buf)
            pdf_bytes = buf.getvalue()
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(pdf_bytes)
        else:
            pdf_bytes = pdf_path.read_bytes()

        response = self.client.post(
            "/api/profile/upload-pdf",
            files={"file": ("master_cv.pdf", pdf_bytes, "application/pdf")},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["filename"], "master_cv.pdf")
        self.assertGreater(data["pages"], 0)
        self.assertGreater(data["word_count"], 0)

        # Check profile has updated fields
        profile = self.client.get("/api/profile").json()
        self.assertEqual(profile["master_cv_filename"], "master_cv.pdf")
        self.assertTrue(len(profile.get("master_cv_text", "")) > 0)


    def test_scraper_config_endpoints(self):
        # GET config
        res = self.client.get("/api/scraper/config")
        self.assertEqual(res.status_code, 200)
        config = res.json()
        self.assertIn("portals", config)
        self.assertIn("keywords", config)
        self.assertIn("levels", config)
        self.assertIn("locations", config)

        # PUT config
        config["keywords"].append("Golang")
        put_res = self.client.put("/api/scraper/config", json=config)
        self.assertEqual(put_res.status_code, 200)
        self.assertTrue(put_res.json()["success"])

        # Re-fetch
        new_config = self.client.get("/api/scraper/config").json()
        self.assertIn("Golang", new_config["keywords"])

    def test_tailor_cv_with_template_option(self):
        # Get first job
        jobs_res = self.client.get("/api/jobs?limit=1")
        jobs = jobs_res.json()["jobs"]
        if not jobs:
            return
        job_id = jobs[0]["id"]

        # Tailor with template modern
        tailor_res = self.client.post(f"/api/jobs/{job_id}/tailor?template=modern")
        self.assertEqual(tailor_res.status_code, 200)
        data = tailor_res.json()
        self.assertTrue(data["success"])
        self.assertIn("used_master_cv", data)
        self.assertIn("applied_rules", data)
        self.assertIn("latex_code", data)

    def test_job_status_and_delete_endpoints(self):
        # 1. Create a dummy job through storage directly or fetch first
        from web.app import storage
        from models.Job import Job
        test_job = Job(
            title="Temporary Test Job For Deletion",
            company="Temporary Tech Corp",
            link="https://temptest.example.com/job/temp",
        )
        storage.save_jobs([test_job])
        jobs, _ = storage.get_jobs(query="Temporary Tech Corp")
        self.assertTrue(len(jobs) > 0)
        job_id = jobs[0]["id"]
        self.assertEqual(jobs[0]["status"], "saved")

        # 2. Test PATCH /api/jobs/{id}/status
        patch_res = self.client.patch(f"/api/jobs/{job_id}/status", json={"status": "rejected"})
        self.assertEqual(patch_res.status_code, 200)
        self.assertTrue(patch_res.json()["success"])
        self.assertEqual(patch_res.json()["status"], "rejected")

        # Verify through GET /api/jobs?status=rejected
        filter_res = self.client.get("/api/jobs?status=rejected")
        self.assertEqual(filter_res.status_code, 200)
        filtered_ids = [j["id"] for j in filter_res.json()["jobs"]]
        self.assertIn(job_id, filtered_ids)

        # 3. Test Invalid status
        bad_patch = self.client.patch(f"/api/jobs/{job_id}/status", json={"status": "invalid_status_xyz"})
        self.assertEqual(bad_patch.status_code, 400)

        # 4. Test DELETE /api/jobs/{id}
        del_res = self.client.delete(f"/api/jobs/{job_id}")
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.json()["success"])

        # 5. Verify job is gone
        get_res = self.client.get(f"/api/jobs/{job_id}")
        self.assertEqual(get_res.status_code, 404)

    def test_settings_endpoints(self):
        # 1. GET settings
        get_res = self.client.get("/api/settings")
        self.assertEqual(get_res.status_code, 200)
        data = get_res.json()
        self.assertIn("gemini_model", data)
        self.assertIn("has_api_key", data)
        self.assertIn("theme", data)

        # 2. PUT settings (update model and key)
        payload = {
            "ai_provider": "gemini",
            "gemini_model": "gemini-1.5-pro",
            "gemini_api_key": "AIzaSyFakeTestKeyForUnitTests999",
            "theme": "light",
        }
        put_res = self.client.put("/api/settings", json=payload)
        self.assertEqual(put_res.status_code, 200)
        put_data = put_res.json()
        self.assertTrue(put_data["success"])
        self.assertEqual(put_data["gemini_model"], "gemini-1.5-pro")
        self.assertTrue(put_data["has_api_key"])
        self.assertEqual(put_data["theme"], "light")

        # 3. Verify via GET /api/settings
        verify_res = self.client.get("/api/settings")
        self.assertEqual(verify_res.status_code, 200)
        vdata = verify_res.json()
        self.assertEqual(vdata["gemini_model"], "gemini-1.5-pro")
        self.assertTrue(vdata["has_api_key"])
        self.assertIn("AIzaSy", vdata["masked_api_key"])

        # 4. Verify via GET /api/stats
        stats_res = self.client.get("/api/stats")
        self.assertEqual(stats_res.status_code, 200)
        self.assertTrue(stats_res.json()["has_gemini_key"])
        self.assertEqual(stats_res.json()["gemini_model"], "gemini-1.5-pro")

    def test_model_catalog_and_connection(self):
        # 1. GET /api/settings/models
        catalog_res = self.client.get("/api/settings/models")
        self.assertEqual(catalog_res.status_code, 200)
        catalog = catalog_res.json()
        self.assertIn("gemini", catalog)
        self.assertIn("openai", catalog)
        self.assertIn("claude", catalog)
        self.assertIn("custom", catalog)

        # Check OpenAI has gpt-3.5-turbo and gpt-4o
        openai_models = [m["id"] for m in catalog["openai"]["models"]]
        self.assertIn("gpt-3.5-turbo", openai_models)
        self.assertIn("gpt-4o", openai_models)

        # Check Claude has 3.5 sonnet
        claude_models = [m["id"] for m in catalog["claude"]["models"]]
        self.assertTrue(any("claude-3-5-sonnet" in m for m in claude_models))

        # 2. PUT settings for OpenAI
        put_openai = self.client.put(
            "/api/settings",
            json={
                "ai_provider": "openai",
                "ai_model": "gpt-3.5-turbo",
                "openai_api_key": "sk-proj-faketestkey1234567890abcdef",
            },
        )
        self.assertEqual(put_openai.status_code, 200)
        pdata = put_openai.json()
        self.assertEqual(pdata["ai_provider"], "openai")
        self.assertEqual(pdata["ai_model"], "gpt-3.5-turbo")
        self.assertTrue(pdata["has_api_key"])
        self.assertIn("sk-pr", pdata["masked_openai_key"])

        # 3. POST /api/settings/test-connection with dummy key
        # (Should return ok=False with clean message and latency, not 500 crash)
        test_res = self.client.post(
            "/api/settings/test-connection",
            json={
                "provider": "openai",
                "api_key": "sk-proj-invalidmockkey99999",
                "model_name": "gpt-3.5-turbo",
            },
        )
        self.assertEqual(test_res.status_code, 200)
        tdata = test_res.json()
        self.assertIn("ok", tdata)
        self.assertIn("latency_ms", tdata)
        self.assertIn("message", tdata)
        self.assertIsInstance(tdata["latency_ms"], int)


if __name__ == "__main__":
    unittest.main()



