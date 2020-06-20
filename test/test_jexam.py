###########################
##### Tests for jExam #####
###########################

import unittest
import os
import shutil
import pathlib

from jexam.parser import main as jexam

bin_globals = {}
with open("bin/jexam") as f:
    exec(f.read(), bin_globals)

TEST_FILES_PATH = pathlib.Path("test")
PARSER = bin_globals["parser"]

class TestJexam(unittest.TestCase):

    def assertFilesEqual(self, p1, p2):
        with open(p1) as f1:
            with open(p2) as f2:
                self.assertEqual(f1.read(), f2.read(), f"Contents of {p1} did not equal contents of {p2}")

    def test_jexam_notebook_seed(self):
        nb_path = str(TEST_FILES_PATH / 'test-exam.ipynb')
        command = [nb_path]
        args = PARSER.parse_args(command)
        jexam(args)

        self.assertTrue(os.path.isdir("dist"), "directory ./dist does not exist")
        self.assertEqual(
            os.listdir("dist"), os.listdir(TEST_FILES_PATH / "dist-correct"), 
            "Contents of ./dist not correct"
        )

        # check that all dist/exam_*/* are correct
        for d1, d2 in zip(os.listdir("dist"), os.listdir(TEST_FILES_PATH / "dist-correct")):
            d1, d2 = os.path.join("dist", d1), os.path.join(TEST_FILES_PATH / "dist-correct", d2)
            self.assertEqual(os.listdir(d1), os.listdir(d2), f"Contents of {d1} not correct")

            # check dist/exam_*/*/*
            for d11, d22 in zip(os.listdir(d1), os.listdir(d2)):
                if os.path.split(d1)[1] == "tests":
                    continue
                d11, d22 = os.path.join(d1, d11), os.path.join(d2, d22)
                self.assertEqual(os.listdir(d11), os.listdir(d22), f"Contents of {d11} not correct")

                # check file contents
                for f1111, f2222 in zip(os.listdir(d11), os.listdir(d22)):
                    f1111, f2222 = os.path.join(d11, f1111), os.path.join(d22, f2222)
                    
                    # if tests dir, look at all files in the directory
                    if os.path.split(f1111)[1] == "tests":
                        for f11111, f22222 in zip(os.listdir(f1111), os.listdir(f2222)):
                            f11111, f22222 = os.path.join(f1111, f11111), os.path.join(f2222, f22222)
                            self.assertFilesEqual(f11111, f22222)
                    
                    # otherwise, check contents
                    else:
                        self.assertFilesEqual(f1111, f2222)
