#!/usr/bin/env python
#
# HPCACMAgent extension
#
# Copyright 2018 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.7+


import os
import sys
import json
import subprocess
import re
import time
import traceback
import socket
import shutil
import platform
import struct
import array
import fcntl
import threading

from Utils.WAAgentUtil import waagent
import Utils.HandlerUtil as Util

#Define global variables
ExtensionShortName = 'HPCACMAgent'
DaemonPidFilePath = '/var/run/hpcacmdaemon.pid'
NMInstallRoot = '/opt/hpcnodemanager'
AgentInstallRoot = '/opt/NodeAgent'
DistroName = None
DistroVersion = None
RestartIntervalInSeconds = 60

def main():
    waagent.LoggerInit('/var/log/waagent.log','/dev/stdout')
    waagent.Log("%s started to handle." %(ExtensionShortName))
    waagent.MyDistro = waagent.GetMyDistro()
    global DistroName, DistroVersion
    distro = platform.dist()
    DistroName = distro[0].lower()
    DistroVersion = distro[1]
    for a in sys.argv[1:]:        
        if re.match("^([-/]*)(disable)", a):
            disable()
        elif re.match("^([-/]*)(uninstall)", a):
            uninstall()
        elif re.match("^([-/]*)(install)", a):
            install()
        elif re.match("^([-/]*)(enable)", a):
            enable()
        elif re.match("^([-/]*)(daemon)", a):
            daemon()            
        elif re.match("^([-/]*)(update)", a):
            update()

def _is_nodemanager_daemon(pid):
    retcode, output = waagent.RunGetOutput("ps -p {0} -o cmd=".format(pid))
    if retcode == 0:
        waagent.Log("The cmd for process {0} is {1}".format(pid, output))
        pattern = r'(.*[/\s])?{0}\s+[-/]*daemon$'.format(os.path.basename(__file__))
        if re.match(pattern, output):
            return True
    waagent.Log("The process {0} is not HPC Linux node manager daemon".format(pid))
    return False

def install_package(package_name):
    if DistroName == "centos" or DistroName == "redhat":
        cmd = "yum -y install " + package_name
    elif DistroName == "ubuntu":
        cmd = "apt-get -y install " + package_name
    elif DistroName == "suse":
        if not os.listdir('/etc/zypp/repos.d'):
            waagent.Run("zypper ar http://download.opensuse.org/distribution/13.2/repo/oss/suse/ opensuse")
            cmd = "zypper -n --gpg-auto-import-keys install --force-resolution -l " + package_name
        else:
            cmd = "zypper -n install --force-resolution -l " + package_name
    else:
        raise Exception("Unsupported Linux Distro.")
    waagent.Log("The command to install {0}: {1}".format(package_name, cmd))
    attempt = 1
    while(True):
        waagent.Log("Installing package {0} (Attempt {1})".format(package_name, attempt))
        retcode, retoutput = waagent.RunGetOutput(cmd)
        if retcode == 0:
            waagent.Log("package {0} installation succeeded".format(package_name))
            break
        else:
            waagent.Log("package {0} installation failed {1}:\n {2}".format(package_name, retcode, retoutput))
            if attempt < 3:
                attempt += 1
                time.sleep(5)
                if DistroName == 'suse' and retcode == 104:
                    waagent.Run("zypper ar http://download.opensuse.org/distribution/13.2/repo/oss/suse/ opensuse")
                    cmd = "zypper -n --gpg-auto-import-keys install --force-resolution -l " + package_name
                continue
            else:
                raise Exception("failed to install package {0}:{1}".format(package_name, retcode))

def _uninstall_nodemanager_files():
    if os.path.isdir(NMInstallRoot):
        for tmpname in os.listdir(NMInstallRoot):
            if tmpname == 'logs':
                continue
            if tmpname == 'certs':
                continue
            if tmpname == 'filters':
                continue
            tmppath = os.path.join(NMInstallRoot, tmpname)
            if os.path.isdir(tmppath):
                shutil.rmtree(tmppath)
            elif os.path.isfile(tmppath):
                os.remove(tmppath)
    if os.path.isdir(AgentInstallRoot):
        shutil.rmtree(AgentInstallRoot)

def _install_cgroup_tool():
    if waagent.Run("command -v cgexec", chk_err=False) == 0:
        waagent.Log("cgroup tools was already installed")
    else:
        waagent.Log("Start to install cgroup tools")
        if DistroName == "ubuntu":
            cg_pkgname = 'cgroup-bin'
        elif (DistroName == "centos" or DistroName == "redhat") and re.match("^6", DistroVersion):
            cg_pkgname = 'libcgroup'
        else:
            cg_pkgname = 'libcgroup-tools'
        install_package(cg_pkgname)
        waagent.Log("cgroup tool was successfully installed")

def _install_psutils():
    _install_gcc()
    _install_pip()
    if waagent.Run("pip install psutil", chk_err=False) == 0:
        waagent.Log("psutil installed")
    else:
        waagent.Log("Error installing psutil")

def _install_pip():
    ec = waagent.Run("curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py --tlsv1.2", chk_err=False)
    if ec != 0:
        waagent.Log("get-pip.py was not downloaded, {0}".format(ec))
        raise Exception("failed to install package python-pip:{0}".format(ec))
    waagent.Log("get-pip.py was downloaded")
    ec = waagent.Run("python get-pip.py", chk_err=False)
    if ec != 0:
        waagent.Log("get-pip.py run failed, {0}".format(ec))
        raise Exception("failed to install package python-pip:{0}".format(ec))
    waagent.Log("python-pip was installed")

def _check_and_install_package(pkg, cmd = None):
    if not cmd:
        cmd = pkg
    if waagent.Run("command -v {0}".format(cmd), chk_err=False) == 0:
        waagent.Log("{0} was already installed".format(pkg))
    else:
        waagent.Log("Start to install {0}".format(pkg))
        install_package(pkg)
        waagent.Log("{0} was successfully installed".format(pkg))

def _install_gcc():
    _check_and_install_package("gcc")

def _install_python_devel():
    _check_and_install_package("python-devel")

def _install_libunwind():
    if DistroName == "ubuntu":
        _check_and_install_package("libunwind8-dev")
    else:
        _check_and_install_package("libunwind")

def _install_sysstat():
    _check_and_install_package("sysstat", "iostat")

def get_networkinterfaces():
    """
    Return the interface name, and ip addr of the
    all non loopback interfaces.
    """
    expected=16 # how many devices should I expect...
    is_64bits = sys.maxsize > 2**32
    struct_size=40 if is_64bits else 32 # for 64bit the size is 40 bytes, for 32bits it is 32 bytes.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    buff=array.array('B', b'\0' * (expected*struct_size))
    retsize=(struct.unpack('iL', fcntl.ioctl(s.fileno(), 0x8912, struct.pack('iL',expected*struct_size,buff.buffer_info()[0]))))[0]
    if retsize == (expected*struct_size) :
        waagent.Log('SIOCGIFCONF returned more than ' + str(expected) + ' up network interfaces.')
    nics = []
    s=buff.tostring()
    for i in range(0,retsize,struct_size):
        iface=s[i:i+16].split(b'\0', 1)[0]
        if iface == b'lo':
            continue
        else:
            nics.append((iface.decode('latin-1'), socket.inet_ntoa(s[i+20:i+24])))
    return nics

def cleanup_host_entries():
    hostsfile = '/etc/hosts'
    if not os.path.isfile(hostsfile):
        return
    try:
        hpcentryexists = False
        newcontent=''
        with open(hostsfile, 'r') as F:
            for line in F.readlines():
                if re.match(r"^[0-9\.]+\s+[^\s#]+\s+#HPCD?\s*$", line):
                    hpcentryexists = True
                else:
                    newcontent += line
        if hpcentryexists:
            waagent.Log("Clean all HPC related host entries from hosts file")
            waagent.ReplaceFileContentsAtomic(hostsfile,newcontent)
            os.chmod(hostsfile, 0o644)
    except :
        raise

def init_suse_hostsfile(host_name, ipaddrs):
    hostsfile = '/etc/hosts'
    if not os.path.isfile(hostsfile):
        return
    try:
        newhpcd_entries = ''
        for ipaddr in ipaddrs:
            newhpcd_entries += '{0:24}{1:30}#HPCD\n'.format(ipaddr, host_name)

        curhpcd_entries = ''
        newcontent = ''
        hpcentryexists = False
        with open(hostsfile, 'r') as F:
            for line in F.readlines():
                if re.match(r"^[0-9\.]+\s+[^\s#]+\s+#HPCD\s*$", line):
                    curhpcd_entries += line
                    hpcentryexists = True
                elif re.match(r"^[0-9\.]+\s+[^\s#]+\s+#HPC\s*$", line):
                    hpcentryexists = True
                else:
                    newcontent += line

        if newhpcd_entries != curhpcd_entries:
            if hpcentryexists:
                waagent.Log("Clean the HPC related host entries from hosts file")
            waagent.Log("Add the following HPCD host entries:\n{0}".format(newhpcd_entries))
            if newcontent and newcontent[-1] != '\n':
                newcontent += '\n'
            newcontent += newhpcd_entries
            waagent.ReplaceFileContentsAtomic(hostsfile,newcontent)
            os.chmod(hostsfile, 0o644)
    except :
        raise

#def gethostname_from_configfile(configfile):
#    config_hostname = None
#    if os.path.isfile(configfile):
#        with open(configfile, 'r') as F:
#            configjson = json.load(F)
#        if 'RegisterUri' in configjson:
#            reguri = configjson['RegisterUri']
#            reguri = reguri[0:reguri.rindex('/')]
#            config_hostname = reguri[reguri.rindex('/')+1:]
#    return config_hostname

def _add_dns_search(domain_fqdn):
    need_update = False
    new_content = ''
    for line in (open('/etc/resolv.conf','r')).readlines():
        if re.match('^search.* {0}'.format(domain_fqdn), line):
            waagent.Log('{0} was already added in /etc/resolv.conf'.format(domain_fqdn))
            return
        if re.match('^search', line):
            need_update = True
            new_content += line.replace('search', 'search {0}'.format(domain_fqdn))
        else:
            new_content += line
    if need_update:
        waagent.Log('Adding {0} to /etc/resolv.conf'.format(domain_fqdn))
        waagent.SetFileContents('/etc/resolv.conf', new_content)

def _update_dns_record(domain_fqdn):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while True:
        try:
            s.connect((domain_fqdn, 53))
            break
        except Exception, e:
            waagent.Log('Failed to connect to {0}:53: {1}'.format(domain_fqdn, e))
    ipaddr = s.getsockname()[0]
    host_fqdn = "{0}.{1}".format(socket.gethostname().split('.')[0], domain_fqdn)
    dns_cmd = 'echo -e "server {0}\nzone {0}\nupdate delete {1}\nupdate add {1} 864000 A {2}\nsend\n" | nsupdate -v'.format(domain_fqdn, host_fqdn, ipaddr)
    waagent.Log('The command to update ip to dns server is: {0}'.format(dns_cmd))
    retry = 0
    while retry < 60:
        dns_ret, dns_msg = waagent.RunGetOutput(dns_cmd)
        if dns_ret == 0:
            waagent.Log("Succeeded to update ip to dns server.")
            return
        else:
            retry = retry + 1
            waagent.Log("Failed to update ip to dns server: {0}, {1}".format(dns_ret, dns_msg))
            time.sleep(10)

def _mount_cgroup():
    if not os.path.isdir('/cgroup'):
        os.mkdir('/cgroup')
    if not os.listdir('/cgroup'):
        retcode, mount_msg = waagent.RunGetOutput('mount -t cgroup cgroup /cgroup')
        waagent.Log("mount /cgroup directory {0}:{1}".format(retcode, mount_msg))
        if retcode == 0:
            waagent.Log("/cgroup directory is successfully mounted.")
        else:
            raise Exception("failed to mount /cgroup directory")
    else:
        waagent.Log("/cgroup directory was already mounted.")

#def config_firewall_rules():
#    if DistroName == 'redhat':
#        waagent.Log('Configuring the firewall rules')
#        major_version = int(DistroVersion.split('.')[0])
#        if major_version < 7:
#            waagent.Run('lokkit --port=40000:tcp --update', chk_err=False)
#        elif waagent.Run("firewall-cmd --state", chk_err=False) == 0:
#            waagent.Run("firewall-cmd --permanent --zone=public --add-port=40000/tcp")
#            waagent.Run("firewall-cmd --reload")

def _subprocess(exec_path_args, work_dir, stdoutfile, stderrfile, logfile):
    hutil = parse_context('Enable', logfile)
    while True:
        try:
            dirname = os.path.dirname(stdoutfile)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            dirname = os.path.dirname(stderrfile)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            with open(stdoutfile, 'a') as out, open(stderrfile, 'a') as err:
                infile = open(os.devnull, 'r')
                child_process = subprocess.Popen(exec_path_args, stdin=infile, stdout=out, stderr=err, cwd=work_dir, shell=True)
                if child_process.pid is None or child_process.pid < 1:
                    exit_msg = 'Failed to start process {0}'.format(exec_path_args)
                    hutil.do_status_report('Enable', 'error', 1, exit_msg)
                else:
                    #Sleep 1 second to check if the process is still running
                    time.sleep(1)
                    if child_process.poll() is None:
                        hutil.do_status_report('Enable', 'success', 0, "")
                        hutil.log('process started {0}'.format(exec_path_args))
                        exit_code = child_process.wait()
                        exit_msg = "process exits: {0} {1}".format(exec_path_args, exit_code)
                        hutil.do_status_report('Enable', 'warning', exit_code, exit_msg)
                    else:
                        exit_msg = "{0} process crashes: {1}".format(exec_path_args, child_process.returncode)
                        hutil.do_status_report('Enable', 'error', child_process.returncode, exit_msg)
                hutil.log(exit_msg)
                time.sleep(RestartIntervalInSeconds)
        except Exception, e:
            hutil.log("start process error {0}".format(e))
            hutil.do_exit(4, 'Start','error','4', '{0}'.format(e))
        hutil.log("Restart process {0} after {1} seconds".format(exec_path_args, RestartIntervalInSeconds))

def parse_context(operation, logfile=None):
    hutil = Util.HandlerUtility(waagent.Log, waagent.Error, ExtensionShortName)
    hutil.do_parse_context(operation, logfile)
    return hutil

def install():
    hutil = parse_context('Install')
    try:
        waagent.Log("Install started.")
        cleanup_host_entries()
        _uninstall_nodemanager_files()
        _install_cgroup_tool()
        _install_libunwind()
        _install_python_devel()
        _install_sysstat()
        _install_psutils()

        # shutil.copytree(srcDir, NMInstallRoot)
        # install the node agent
        srcDir = os.path.join(os.getcwd(), "NodeAgent")
        waagent.Log("copy from {0} to {1}".format(srcDir, AgentInstallRoot))
        shutil.copytree(srcDir, AgentInstallRoot)
        waagent.Log("copied")

        logDir = os.path.join(NMInstallRoot, "logs")
        waagent.Log("Testing {0}".format(logDir))
        if not os.path.isdir(logDir):
            os.makedirs(logDir)
        srcDir = os.path.join(os.getcwd(), "hpcnodemanager")
        waagent.RunGetOutput("chmod +x {0}/*".format(srcDir))
        waagent.RunGetOutput("chmod +x {0}/lib/*".format(srcDir))
        
        for filename in os.listdir(srcDir):
            srcname = os.path.join(srcDir, filename)
            destname = os.path.join(NMInstallRoot, filename)
            if os.path.isfile(srcname):
                shutil.copy2(srcname, destname)
            elif os.path.isdir(srcname):
                shutil.copytree(srcname, destname)

       # public_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('publicSettings')
        # TODO passin the sas token
#        host_name = None
#        if public_settings:
#            host_name = public_settings.get('HostName')
#        backup_configfile = os.path.join(os.getcwd(), 'nodemanager.json')
#        if not host_name:
#            # if there is backup nodemanager.json, means it is an update install, if 'HostName' not defined in the extension
#            # settings, we shall get from the backup nodemanager.json
#            if os.path.isfile(backup_configfile):
#                waagent.Log("Backup nodemanager configuration file found")
#                host_name = gethostname_from_configfile(backup_configfile)
#
#        curhostname = socket.gethostname().split('.')[0]
#        if host_name:
#            if host_name.lower() != curhostname.lower():
#                waagent.Log("HostName was set: hostname from {0} to {1}".format(curhostname, host_name))
#                waagent.MyDistro.setHostname(host_name)
#                waagent.MyDistro.publishHostname(host_name)
#        else:
#            host_name = curhostname
#        public_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('publicSettings')
#        cluster_connstring = public_settings.get('ClusterConnectionString')
#        if not cluster_connstring:
#            waagent.Log("ClusterConnectionString is not specified")
#            protect_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('protectedSettings')
#            cluster_connstring = protect_settings.get('ClusterName')
#            if not cluster_connstring:
#                error_msg = "neither ClusterConnectionString nor ClusterName is specified."
#                hutil.error(error_msg)
#                raise ValueError(error_msg)
#        ssl_thumbprint = public_settings.get('SSLThumbprint')
#        if not ssl_thumbprint:
#            api_prefix = "http://{0}:80/HpcLinux/api/"
#            listen_uri = "http://0.0.0.0:40000"
#        else:
#            #TODO: import the ssl certificate for hpc nodemanager
#            api_prefix = "https://{0}:443/HpcLinux/api/"
#            listen_uri = "https://0.0.0.0:40002"
#        node_uri = api_prefix + host_name + "/computenodereported"
#        reg_uri = api_prefix + host_name + "/registerrequested"
#        hostsfile_uri = api_prefix + "hostsfile"
#        metric_ids_uri = api_prefix + host_name + "/getinstanceids"
#        namingSvcUris = ['https://{0}:443/HpcNaming/api/fabric/resolve/singleton/'.format(h.strip()) for h in cluster_connstring.split(',')]
#        if os.path.isfile(backup_configfile):
#            with open(backup_configfile, 'r') as F:
#                configjson = json.load(F)
#            configjson["NamingServiceUri"] = namingSvcUris
#            configjson["HeartbeatUri"] = node_uri
#            configjson["RegisterUri"] = reg_uri
#            configjson["HostsFileUri"] = hostsfile_uri
#            configjson["MetricInstanceIdsUri"] = metric_ids_uri,
#            configjson["MetricUri"] = ""
#        else:
#            configjson = {
#              "ConfigVersion": "1.0",
#              "NamingServiceUri": namingSvcUris,
#              "HeartbeatUri": node_uri,
#              "RegisterUri": reg_uri,
#              "MetricUri": "",
#              "MetricInstanceIdsUri": metric_ids_uri,
#              "HostsFileUri": hostsfile_uri,
#              "HostsFetchInterval": 120,
#              "ListeningUri": "http://0.0.0.0:40000",
#              "DefaultServiceName": "SchedulerStatefulService",
#              "UdpMetricServiceName": "MonitoringStatefulService"
#            }
#        configfile = os.path.join(NMInstallRoot, 'nodemanager.json')
#        waagent.SetFileContents(configfile, json.dumps(configjson))
#        shutil.copy2(configfile, backup_configfile)
#        config_firewall_rules()
        hutil.do_exit(0, 'Install', 'success', '0', 'Install Succeeded.')
    except Exception, e:
        waagent.Log("Install error {0}.".format(e))
        hutil.do_exit(1, 'Install','error','1', '{0}'.format(e))

def enable():
    hutil = parse_context('Enable')
    try:
        #Check whether monitor process is running.
        #If it does, return. Otherwise clear pid file
        hutil.log("enable() called.")
        if os.path.isfile(DaemonPidFilePath):
            pid = waagent.GetFileContents(DaemonPidFilePath)
            hutil.log("Discovered daemon pid: {0}".format(pid))
            if os.path.isdir(os.path.join("/proc", pid)) and _is_nodemanager_daemon(pid):
                if hutil.is_seq_smaller():
                    hutil.log("Sequence is smaller skip killing")
                    hutil.do_exit(0, 'Enable', 'success', '0', 
                                'HPC Linux node manager daemon is already running')
                else:
                    hutil.log("Stop old daemon: {0}".format(pid))
                    os.killpg(int(pid), 9)
            hutil.log("Remove the daemon pid file: {0}".format(DaemonPidFilePath))
            os.remove(DaemonPidFilePath)

        args = [os.path.join(os.getcwd(), __file__), "daemon"]
        devnull = open(os.devnull, 'w')
        hutil.log("Starting daemon process")
        child = subprocess.Popen(args, stdout=devnull, stderr=devnull, preexec_fn=os.setsid)
        if child.pid is None or child.pid < 1:
            hutil.log("failed to start the daemon process")
            hutil.do_exit(1, 'Enable', 'error', '1',
                        'Failed to launch HPC Linux node manager daemon')
        else:
            hutil.log("started the daemon process, save seq")
            hutil.save_seq()
            hutil.log("started the daemon process, save pid {0}".format(child.pid))
            waagent.SetFileContents(DaemonPidFilePath, str(child.pid))
            #Sleep 3 seconds to check if the process is still running
            time.sleep(3)
            if child.poll() is None:
                hutil.log("3 seconds later, success, Daemon pid: {0}".format(child.pid))
                hutil.do_exit(0, 'Enable', 'success', '0',
                        'HPC Linux node manager daemon is enabled')
            else:
                hutil.log("3 seconds later, failed, Daemon pid: None")
                hutil.do_exit(3, 'Enable', 'error', '3',
                        'Failed to launch HPC Linux node manager daemon')
    except Exception, e:
        hutil.log("Failed to enable the extension with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(2, 'Enable','error','2', "Enable failed. {0} {1}".format(str(e), traceback.format_exc()))

def daemon():
    hutil = parse_context('Enable','daemon.log')
    try:
        hutil.log("Started daemon")
#        public_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('publicSettings')
#        cluster_connstring = public_settings.get('ClusterConnectionString')
#        if not cluster_connstring:
#            waagent.Log("ClusterConnectionString is not specified, use ClusterName instead")
#            protect_settings = hutil._context._config['runtimeSettings'][0]['handlerSettings'].get('protectedSettings')
#            cluster_connstring = protect_settings.get('ClusterName')
#        headnode_name = cluster_connstring.split(',')[0].strip()
#        if headnode_name.find('.') > 0:
#            # The head node name is FQDN, extract the domain FQDN
#            domain_fqdn = headnode_name.split(".", 1)[1]
#            waagent.Log("The domain FQDN is " + domain_fqdn)
#            _add_dns_search(domain_fqdn)
#            #thread.start_new_thread(_update_dns_record, (domain_fqdn,))

        # A fix only for SUSE Linux that sometimes the hostname got changed because out-of-date host/IP entry in /etc/hosts
        # It may happen when the node was assigned a different IP after deallocation
        # We shall clean the current HPC related host/IP entries and add the actual IPs before fetching the hosts file from head node.
#        if DistroName == 'suse':
#            configfile = os.path.join(InstallRoot, 'nodemanager.json')
#            confighostname = gethostname_from_configfile(configfile)
#            curhostname = socket.gethostname().split('.')[0]
#            if confighostname.lower() != curhostname.lower():
#                cleanup_host_entries()
#                waagent.Log("Correct the hostname from {0} to {1}".format(curhostname, confighostname))
#                waagent.MyDistro.setHostname(confighostname)
#                waagent.MyDistro.publishHostname(confighostname)
#            retry = 0
#            while True:
#                nics = get_networkinterfaces()
#                if len(nics) > 0:
#                    init_suse_hostsfile(confighostname, [nic[1] for nic in nics])
#                    break
#                elif retry < 30:
#                    waagent.Log("Failed to get network interfaces information, retry later ...")
#                    time.sleep(2)
#                    retry = retry + 1
#                else:
#                    waagent.Log("Failed to get network interfaces information, just clean")
#                    break
        # Mount the directory /cgroup for centos 6.*
        major_version = int(DistroVersion.split('.')[0])
        if (DistroName == 'centos' or DistroName == 'redhat') and major_version < 7:
            _mount_cgroup()

        exe_path = os.path.join(NMInstallRoot, "nodemanager")

        threadnm = threading.Thread(target=_subprocess, args=(exe_path, NMInstallRoot, os.path.join(hutil.get_log_dir(), "nodemanager.txt"), os.path.join(hutil.get_log_dir(), "nodemanager.err"), "nodemanager.log"))
        threadagent = threading.Thread(target=_subprocess, args=(os.path.join(AgentInstallRoot, "NodeAgent"), AgentInstallRoot, os.path.join(hutil.get_log_dir(), "nodeagent.txt"), os.path.join(hutil.get_log_dir(), "nodeagent.err"), "nodeagent.log"))
        hutil.log("Starting threads")
        threadnm.start()
        threadagent.start()
        hutil.log("Started threads")
        threadnm.join()
        threadagent.join()
        hutil.log("Exited join threads")
        
    except Exception, e:
        hutil.error("Failed to start the daemon with error: %s, stack trace: %s" %(str(e), traceback.format_exc()))
        hutil.do_exit(2, 'Enable','error','2', 'Enable failed.')

def uninstall():
    # TODO where to kill the node manager
    hutil = parse_context('Uninstall')
    _uninstall_nodemanager_files()
    cleanup_host_entries()
    hutil.do_exit(0,'Uninstall','success','0', 'Uninstall succeeded')

def disable():
    waagent.Log("disable() called.")
    hutil = parse_context('Disable')
    #TODO where to kill the node manager
    #Check whether monitor process is running.
    #If it does, kill it. Otherwise clear pid file
    if os.path.isfile(DaemonPidFilePath):
        pid = waagent.GetFileContents(DaemonPidFilePath)
        waagent.Log("Discovered daemon pid: {0}".format(pid))
        if os.path.isdir(os.path.join("/proc", pid)) and _is_nodemanager_daemon(pid):
            waagent.Log(("Stop HPC node manager daemon: {0}").format(pid))
            os.killpg(int(pid), 9)
            cleanup_host_entries()
            hutil.do_exit(0, 'Disable', 'success', '0',
                          'HPC node manager daemon is disabled')
        waagent.Log("Remove the daemon pid file: {0}".format(DaemonPidFilePath))
        os.remove(DaemonPidFilePath)
    else:
        waagent.Log("No daemon pid file discovered.")

    hutil.do_exit(0, 'Disable', 'success', '0',
                  'HPC node manager daemon disabled')

def update():
    hutil = parse_context('Update')
    cleanup_host_entries()
    # TODO: where is the binary update?
#    configfile = os.path.join(InstallRoot, 'nodemanager.json')
#    if os.path.isfile(configfile):
#        waagent.Log("Update extension: backup the nodemanager configuration file.")
#        shutil.copy2(configfile, os.getcwd())
#        # A fix only for SUSE Linux that sometimes the hostname got changed because out-of-date host/IP entry in /etc/hosts
#        # It may happen when the node was assigned a different IP after deallocation
#        if DistroName == 'suse':
#            confighostname = gethostname_from_configfile(configfile)
#            if confighostname:
#                curhostname = socket.gethostname().split('.')[0]
#                if confighostname.lower() != curhostname.lower():
#                    waagent.Log("Update: Set the hostname from {0} to {1}".format(curhostname, confighostname))
#                    waagent.MyDistro.setHostname(confighostname)
#                    waagent.MyDistro.publishHostname(confighostname)
    hutil.do_exit(0,'Update','success','0', 'Update Succeeded')

if __name__ == '__main__' :
    main()

