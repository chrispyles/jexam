###########################
##### Tests for jExam #####
###########################

import unittest
import os
import io
import shutil
import pathlib

from contextlib import redirect_stdout
from textwrap import dedent

from jexam.parser import main as jexam

bin_globals = {"__name__": "__not_main__"}
with open("bin/jexam") as f:
    exec(f.read(), bin_globals)

TEST_FILES_PATH = pathlib.Path("test")
PARSER = bin_globals["parser"]

class TestJexam(unittest.TestCase):

    expected_stdout = dedent("""\
    Generating exam 50
    Generating exam 100
    """)

    def assertFilesEqual(self, p1, p2):
        with open(p1) as f1:
            with open(p2) as f2:
                self.assertEqual(f1.read(), f2.read(), f"Contents of {p1} did not equal contents of {p2}")

    def assertDirsEqual(self, dir1, dir2):
        self.assertTrue(os.path.exists(dir1), f"{dir1} does not exist")
        self.assertTrue(os.path.exists(dir2), f"{dir2} does not exist")
        self.assertTrue(os.path.isfile(dir1) == os.path.isfile(dir2), f"{dir1} and {dir2} have different type")

        if os.path.isfile(dir1):
            self.assertFilesEqual(dir1, dir2)
        else:
            self.assertEqual(os.listdir(dir1), os.listdir(dir2), f"{dir1} and {dir2} have different contents")
            for f1, f2 in zip(os.listdir(dir1), os.listdir(dir2)):
                f1, f2 = os.path.join(dir1, f1), os.path.join(dir2, f2)
                self.assertDirsEqual(f1, f2)

    def run_and_check_jexam(self, seed=None, ok=False):
        nb_path = str(TEST_FILES_PATH / 'test-exam.ipynb')
        command = [nb_path]
        if seed is not None:
            command += ["-s", str(seed)]
        if ok:
            command += ["--format", "ok"]
        args = PARSER.parse_args(command)
        jexam(args)

        correct_dir = "dist-correct" if seed is None else f"dist-correct-{seed}"
        if ok:
            correct_dir += "-ok"

        self.assertDirsEqual("dist", TEST_FILES_PATH / correct_dir)

    def test_notebook_seed(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.run_and_check_jexam()
        self.assertEqual(stdout.getvalue().strip(), type(self).expected_stdout.strip(), "Process stdout incorrect")
    
    def test_notebook_ok(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.run_and_check_jexam(ok=True)
        self.assertEqual(stdout.getvalue().strip(), type(self).expected_stdout.strip(), "Process stdout incorrect")
    
    def test_seed_150(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.run_and_check_jexam(150)
        self.assertEqual(stdout.getvalue().strip(), type(self).expected_stdout.strip(), "Process stdout incorrect")
    
    def tearDown(self):
        if os.path.exists("dist"):
            shutil.rmtree("dist")
