from __future__ import annotations

from io import StringIO
import logging
import unittest


class LoggingStyleTests(unittest.TestCase):
    def test_timing_and_progress_use_stage_banners_and_status_lines(self) -> None:
        from aurora_translator.shared.logging import (
            BANNER_WIDTH,
            ProgressReporter,
            LOG_FORMAT,
            PROJECT_DISPLAY_NAME,
            log_run_complete,
            log_run_start,
            log_timing,
        )

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger("aurora_translator.tests.logging_style")
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)

        log_run_start(logger, "sample run", log_path="logs/test.log", source="input")
        with log_timing(
            logger,
            "load source",
            banner=True,
            heartbeat=False,
            source="input",
        ):
            pass
        reporter = ProgressReporter(
            logger,
            "Serialize items",
            total=2,
            min_log_spacing_seconds=0,
        )
        reporter.update(1)
        log_run_complete(logger, "sample run")

        output = stream.getvalue()
        self.assertIn("*" * BANNER_WIDTH, output)
        self.assertIn(PROJECT_DISPLAY_NAME, output)
        self.assertEqual(output.count(PROJECT_DISPLAY_NAME), 1)
        self.assertIn("Sample run", output)
        self.assertIn("Load source", output)
        self.assertIn("Run started: Sample run", output)
        self.assertIn("Log file: logs/test.log", output)
        self.assertIn("Start: Load source source=input", output)
        self.assertIn("Done: Load source elapsed=", output)
        self.assertIn("Progress: Serialize items processed=1/2", output)
        self.assertIn("Run completed: Sample run", output)
        formatted = logging.Formatter(LOG_FORMAT).format(
            logging.LogRecord(
                "aurora_translator.tests.logging_style",
                logging.INFO,
                __file__,
                1,
                "message",
                (),
                None,
            )
        )
        self.assertIn("[INFO] message", formatted)


if __name__ == "__main__":
    unittest.main()
