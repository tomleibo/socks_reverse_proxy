
# How to compile Sphinx
*Make sure you have Sphinx package installed: pip3 install -U Sphinx.
*Enter 'docs' folder and run this command: sphinx-quickstart
*Answer on all the questions
*Edit conf.py and uncomment 3 Python line at Path Setup.
*Change the abspath form '.' to '..' and save the changes.
*At 'docs' folder run the following command: sphinx-apidoc -o . ..
*It's will create the .rst files.
*Run: make html
*Open index.html and enjoy!