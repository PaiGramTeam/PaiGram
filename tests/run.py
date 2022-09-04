import os
import unittest

main_suite = unittest.TestSuite()

for parent, dirs, _ in os.walk("."):
    for dirname in dirs:
        if dirname == "__pycache__":
            continue
        discover = unittest.defaultTestLoader.discover(
            start_dir=parent + os.sep + dirname, pattern='test_*.py',
            top_level_dir=parent + os.sep + dirname)
        main_suite.addTest(discover)


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(main_suite)
