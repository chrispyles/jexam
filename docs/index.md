# jExam Documentation

```eval_rst
.. toctree::
   :maxdepth: 1
   :caption: Contents:
   :hidden:

   
```

jExam is an exam generation tool that uses Jupyter Notebooks to create multiple versions of interactive exams based on a master Jupyter Notebook. jExam is a fork of [jAssign](https://github.com/okpy/jassic) and [Otter Assign](https://otter-grader.rtfd.io) that uses raw cells in notebooks to define questions with multiple versions, allowing instructors to create anywhere from a few different versions of an exam to an individual versions per student (provided enough questions and versions) for the purpose of preventing illicit collaboration on exams. 

jExam works with different autograders to facilitate the easy grading of submissions, including [Otter Grader](https://otter-grader.rtfd.io) and [OkPy](https://okpy.org). It includes support for both autograded and manually-graded questions, and generates the requisite files for setting up autograders like Gradescope and OkPy. 

## Installation

To install jExam, use pip:

```
pip install jexam
```

If you are also going to be using Otter and Gradescope, you will need to install Otter so that the configuration zip files can be generated.

```
pip install otter-grader
```
