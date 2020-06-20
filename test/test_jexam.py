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

bin_globals = {}
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

    def run_and_check_jexam(self, seed=None):
        nb_path = str(TEST_FILES_PATH / 'test-exam.ipynb')
        command = [nb_path]
        if seed is not None:
            command += ["-s", str(seed)]
        args = PARSER.parse_args(command)
        jexam(args)

        correct_dir = "dist-correct" if seed is None else f"dist-correct-{seed}"

        self.assertTrue(os.path.isdir("dist"), "directory ./dist does not exist")
        self.assertEqual(
            os.listdir("dist"), os.listdir(TEST_FILES_PATH / correct_dir), 
            "Contents of ./dist not correct"
        )

        # check that all dist/exam_*/* are correct
        for d1, d2 in zip(os.listdir("dist"), os.listdir(TEST_FILES_PATH / correct_dir)):
            d1, d2 = os.path.join("dist", d1), os.path.join(TEST_FILES_PATH / correct_dir, d2)
            self.assertEqual(os.listdir(d1), os.listdir(d2), f"Contents of {d1} not correct")

            # check dist/exam_*/*/*
            for d11, d22 in zip(os.listdir(d1), os.listdir(d2)):
                if os.path.split(d1)[1] == "tests":
                    continue
                d11, d22 = os.path.join(d1, d11), os.path.join(d2, d22)
                
                empty_tests = "tests" in os.listdir(d11) and len(os.listdir(os.path.join(d11, "tests"))) == 0

                if not empty_tests:
                    self.assertEqual(os.listdir(d11), os.listdir(d22), f"Contents of {d11} not correct")
                else:
                    d11_contents, d22_contents = os.listdir(d11), os.listdir(d22)
                    d11_contents.remove("tests")
                    try:
                        d22_contents.remove("tests")
                    except ValueError:
                        pass
                    self.assertEqual(d11_contents, d22_contents, f"Contents of {d11} not correct")

                # check file contents
                for f1111, f2222 in zip(os.listdir(d11), os.listdir(d22)):
                    f1111, f2222 = os.path.join(d11, f1111), os.path.join(d22, f2222)
                    
                    # if tests dir, look at all files in the directory
                    if os.path.split(f1111)[1] == "tests" and not empty_tests:
                        for f11111, f22222 in zip(os.listdir(f1111), os.listdir(f2222)):
                            f11111, f22222 = os.path.join(f1111, f11111), os.path.join(f2222, f22222)
                            self.assertFilesEqual(f11111, f22222)
                    
                    # otherwise, check contents
                    elif not empty_tests:
                        self.assertFilesEqual(f1111, f2222)

    def test_notebook_seed(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.run_and_check_jexam()
        self.assertEqual(stdout.getvalue().strip(), type(self).expected_stdout.strip(), "Process stdout incorrect")
    
    def test_seed_150(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.run_and_check_jexam(150)
        self.assertEqual(stdout.getvalue().strip(), type(self).expected_stdout.strip(), "Process stdout incorrect")
    
    def tearDown(self):
        if os.path.exists("dist"):
            shutil.rmtree("dist")
