import unittest

from app.utils.video import extract_youtube_video_id


class ExtractYouTubeVideoIdTest(unittest.TestCase):
    def test_supported_youtube_urls(self):
        cases = {
            "https://www.youtube.com/watch?v=VIDEO_ID": "VIDEO_ID",
            "https://www.youtube.com/watch?v=VIDEO_ID&t=10s": "VIDEO_ID",
            "https://www.youtube.com/watch?v=VIDEO_ID?si=abc": "VIDEO_ID",
            "https://www.youtube.com/watch?si=abc&v=VIDEO_ID": "VIDEO_ID",
            "https://youtu.be/VIDEO_ID": "VIDEO_ID",
            "https://youtu.be/VIDEO_ID?si=abc": "VIDEO_ID",
            "https://www.youtube.com/embed/VIDEO_ID": "VIDEO_ID",
            "https://www.youtube.com/embed/VIDEO_ID?si=abc": "VIDEO_ID",
            "https://www.youtube.com/shorts/VIDEO_ID": "VIDEO_ID",
            "https://www.youtube.com/shorts/VIDEO_ID?si=abc": "VIDEO_ID",
            "https://youtube.com/live/VIDEO_ID?si=abc": "VIDEO_ID",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(extract_youtube_video_id(url), expected)

    def test_invalid_youtube_url(self):
        self.assertIsNone(extract_youtube_video_id("https://example.com/watch?v=VIDEO_ID"))
        self.assertIsNone(extract_youtube_video_id("https://www.youtube.com/watch?si=abc"))
        self.assertIsNone(extract_youtube_video_id(""))
        self.assertIsNone(extract_youtube_video_id(None))


if __name__ == "__main__":
    unittest.main()
