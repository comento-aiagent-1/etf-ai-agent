import io
import logging
import unittest

from src.services.diagnostic_logging import log_safe_exception


class SafeExceptionLoggingTests(unittest.TestCase):
    def test_logs_type_and_location_without_exception_message(self):
        stream = io.StringIO()
        logger = logging.Logger("safe-exception-test")
        logger.setLevel(logging.ERROR)
        logger.addHandler(logging.StreamHandler(stream))

        try:
            raise RuntimeError("sensitive-placeholder")
        except RuntimeError as error:
            log_safe_exception(logger, "test stage", error)

        output = stream.getvalue()
        self.assertIn("RuntimeError", output)
        self.assertIn("test_diagnostic_logging.py", output)
        self.assertNotIn("sensitive-placeholder", output)


if __name__ == "__main__":
    unittest.main()
