import setuptools

with open("README.md", "r") as fh:
	long_description = fh.read()

with open("requirements.txt") as f:
	install_requires = f.read().split("\n")

setuptools.setup(
	name = "jexam",
	version = "0.0.1",
	author = "Chris Pyles",
	author_email = "cpyles@berkeley.edu",
	description = "Jupyter Notebook exa, generator",
	long_description = long_description,
	long_description_content_type = "text/markdown",
	url = "https://github.com/chrispyles/jexam",
	license = "BSD-3-Clause",
	packages = setuptools.find_packages(),
	classifiers = [
		"Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
	],
	install_requires = install_requires,
	scripts=["bin/jexam"],
)
