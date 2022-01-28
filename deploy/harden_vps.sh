port1=43532
port2=63918
port3=3372
port4=13964
port5=55347
port6=5604
peer_port1=3080
peer_port2=12814
peer_port3=32313
peer_port4=58424
peer_port5=56236
peer_port6=8193

peersport=8000
interface=eth0
frontend_ip=95.174.64.9
storm_ip=95.174.64.9
frontend_port=8443
storm_port=10000

ssh=`seq 2000 65000 | sort -R | head -n 1`
/usr/bin/apt-get update
/usr/bin/apt-get upgrade -y && /usr/bin/apt-get dist-upgrade -y
/usr/bin/apt-get install -y iptables-persistent netfilter-persistent fail2ban knockd
echo "ssh"
sed -i "s/^#\?Port\s[0-9]\+/Port $ssh/g" /etc/ssh/sshd_config
echo "***  new ssh port $ssh  ***"
service ssh restart || { echo 'ssh restart failed' ; exit 1; }
echo "knock"
echo > /etc/knockd.conf
/bin/cat >> /etc/knockd.conf << EOL
[options]
                UseSyslog
                logfile = /var/log/knockd.log
                interface = $interface
[openSSH]
                sequence    = $port1:udp,$port2:udp,$port3:udp,$port4:udp,$port5:udp,$port6:udp
                seq_timeout = 15
                command     = /sbin/iptables -w 5 -I INPUT 1 -s %IP% -p tcp --dport $ssh -j ACCEPT
                tcpflags    = syn
                cmd_timeout = 120
                stop_command = /sbin/iptables -w 5 -D INPUT -s %IP% -p tcp --dport $ssh -j ACCEPT

[peer]
                sequence    = $peer_port1:tcp,$peer_port2:tcp,$peer_port3:tcp,$peer_port4:tcp,$peer_port5:tcp,$peer_port6:tcp
                seq_timeout = 15
                command     = /sbin/iptables -w 5 -I INPUT 1 -s %IP% -p tcp --dport $peersport -j ACCEPT
                tcpflags    = syn
                cmd_timeout = 120
                stop_command = /sbin/iptables -w 5 -D INPUT -s %IP% -p tcp --dport $peersport -j ACCEPT
EOL
echo > /etc/default/knockd
/bin/cat >> /etc/default/knockd << EOL
START_KNOCKD=1
KNOCKD_OPTS="-i $interface"

EOL
/usr/sbin/service knockd restart || { echo 'knockd restart failed' ; exit 1; }

echo "iptables"
/usr/sbin/service netfilter-persistent flush || { echo 'netfilter persist failed' ; exit 1; }
echo ':msg,contains, "IPTABLES" /var/log/iptables.log' > /etc/rsyslog.d/10-iptables.conf ; service rsyslog restart;
iptables -N LOGGING_INPUT || { echo 'IPtables command failed (1)' ; exit 1; }
iptables -N LOGGING_OUTPUT || { echo 'IPtables command failed (2)' ; exit 1; }
iptables -N LOGGING_FORWARD || { echo 'IPtables command failed (3)' ; exit 1; }
iptables -A INPUT -i lo -j ACCEPT || { echo 'IPtables command failed (4)' ; exit 1; }
iptables -A INPUT -i $interface -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT || { echo 'IPtables command failed (5)' ; exit 1; }
iptables -A INPUT -j LOGGING_INPUT || { echo 'IPtables command failed (6)' ; exit 1; }
iptables -A INPUT -j DROP || { echo 'IPtables command failed (7)' ; exit 1; }
iptables -A OUTPUT -o $interface -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT || { echo 'IPtables command failed (7.5)' ; exit 1; }
iptables -A OUTPUT -o lo -j ACCEPT || { echo 'IPtables command failed (8)' ; exit 1; }
iptables -A OUTPUT -j LOGGING_OUTPUT || { echo 'IPtables command failed (9)' ; exit 1; }
iptables -A LOGGING_INPUT -m limit --limit 100/min -j LOG --log-prefix "IPTABLES_INPUT_DROP: " --log-level 7 || { echo 'IPtables command failed (10)' ; exit 1; }
iptables -A LOGGING_INPUT -j DROP || { echo 'IPtables command failed (11)' ; exit 1; }

echo "ipset"
ipset create PERMIT_IPS hash:ip timeout
iptables -I INPUT -j PERMIT_IPS
iptables -A PERMIT_IPS -p tcp --dports 8000  -m set --match-set PERMIT_IPS -j EXTEND
iptables -A PERMIT_IPS -j RETURN
iptables -A EXTEND -j SET --add-set PERMIT_IPS src --exist --timeout 18000
iptables -A EXTEND -j ACCEPT


echo "*** opening ports for storm and frontend ***"
iptables -I INPUT 1 -s $storm_ip -p tcp --dport $storm_port -j ACCEPT || { echo 'IPtables command failed (12)' ; exit 1; }
iptables -I INPUT 1 -s $frontend_ip -p tcp --dport $frontend_port -j ACCEPT || { echo 'IPtables command failed (13)' ; exit 1; }
/usr/sbin/service netfilter-persistent save || { echo 'netfilter persist save failed ' ; exit 1; }
/bin/systemctl daemon-reload || { echo 'daemon reload failed' ; exit 1; }
echo ""
echo "*****************************"
echo "    New SSH port is: $ssh    "
echo "*****************************"
echo ""

echo "*** replacing logrotate.conf ***"
cp deploy/logrotate.conf logrotate.conf /etc/
if [echo $?]; then
  echo "*** logrotate.conf replaced successfully***"
else 
  echo "*** problem to replace logrotate.conf !***"

fi