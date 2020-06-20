#################################
##### jExam Argument Parser #####
#################################

import argparse

def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("master", type=str, help="Path to exam master notebook")
    parser.add_argument("result", nargs="?", default="dist", help="Path at which to write output notebooks")
    parser.add_argument("-f", "--format", type=str, default="otter", help="Name of autograder format; 'otter' or 'ok'")
    parser.add_argument("-s", "--seed", type=int, default=None, help="Random seed for NumPy to run before execution")
    parser.add_argument("-q", "--quiet", default=False, action="store_true", help="Run without printing status")
    return parser
