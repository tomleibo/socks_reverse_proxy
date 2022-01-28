cd ~/dev/work/appxbackend
source venv/bin/activate
cd ../infra
python3 setup.py sdist
cd dist
pip install `ls -t infra* | head -1`