# Steps to deploy backend

### Copy the project into /root/appxbackend
```shell script
knock -u 178.62.30.34 43532 63918 3372 13964 55347 5604
scp -P 14450 -r ~/dev/work/appxbackend root@178.62.30.34:/root/appxbackend
```

### Copy the infra.tar.gz 
```shell script
scp -P 14450 infra-0.0.3.tar.gz root@178.62.30.34:/root/infra.tar.gz
```

### Create a venv and install all dependencies
```shell script
apt-get install python3-venv
cd /root/appxbackend
python3 -m venv venv
source venv/bin/activate
pip install /root/infra.tar.gz
pip install -r build_files/requirements.txt 
```



### Install MongoDB
```shell script
wget -qO - https://www.mongodb.org/static/pgp/server-4.2.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu bionic/mongodb-org/4.2 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.2.list
sudo apt-get update
sudo apt-get install -y mongodb-org
mkdir -p /data/db/
systemctl start mongod
```

### Harden the VPS using the script
- set the port knock sequences, ports and IPs
- run the script `deploy/harden_vps.sh`
- save the ssh port in the keepass

### Run the server as service
- copy the service file into the system dir:
```shell script
cp /root/appxbackend/deploy/dirtysocks.service /etc/systemd/system/
``` 
- systemctl daemon-reload
- systemctl start dirtysocks

