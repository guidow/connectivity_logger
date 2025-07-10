#!/usr/bin/env python
'''
Short script for logging your internet connectivity history in a CSV file. The intention
is to gather data to tell allow you to tell objectively how reliable your ISP really is
and allow you to compare that data to others.
Intended to be run as a cron job.
Only ping tests are supported at the moment. HTTPS connection tests are planned next.

Copyright © 2021 Guido Winkelmann

Licensed under the terms of the GNU General Public License version 2

@package connectivity_logger
'''

import socket
import re
import time
import os
from datetime import datetime, timezone
from configparser import ConfigParser
from enum import Enum
from subprocess import Popen, PIPE, TimeoutExpired
from ipaddress import ip_address

CheckResult = Enum("CheckResult",
                   ["OK",
                    "UNREACHABLE",
                    "UNRESOLVABLE",
                    "PACKET_LOSS",
                    "UNROUTABLE_IP",
                    "BAD_CERTIFICATE",
                    "UNKNOWN"])

ping_summary_regex = re.compile(r"(\d+) packets transmitted, (\d+) received, (\d+)")

class PingCheck:
    def __init__(self, name, configuration_section, num_pings, interval):
        self.name = name
        self.protocol = configuration_section.get("protocol", "any")
        self.hostname = configuration_section["hostname"]
        self.non_global_okay = configuration_section.getboolean("non_global_okay", False)
        self.num_pings = num_pings
        self.interval = interval
        
        self.used_address = ""
        self.used_protocol = ""

    def start_check(self):
        try:
            addresses = socket.getaddrinfo(self.hostname, None)
        except socket.gaierror:
            return
        for address in addresses:
            family, sock_type, proto, _, sockaddr = address
            current_address, *_ = sockaddr
            if (sock_type == socket.SocketKind.SOCK_RAW and
                not hasattr(self, "process")):
                    if (family == socket.AddressFamily.AF_INET and 
                        self.protocol in ["ipv4", "any"]):
                            self.process = Popen(
                                ["ping", "-c", str(self.num_pings), "-i", str(self.interval), current_address],
                                stdout=PIPE,
                                env={"LC_ALL": "C", "LANG": "C"})
                            self.used_address = ip_address(current_address)
                            self.used_protocol = "ipv4"

                    if (family == socket.AddressFamily.AF_INET6 and 
                        self.protocol in ["ipv6", "any"]):
                            self.process = Popen(
                                ["ping6", "-c", str(self.num_pings), "-i", str(self.interval), current_address],
                                stdout=PIPE,
                                env={"LC_ALL": "C", "LANG": "C"})
                            self.used_address = ip_address(current_address)
                            self.used_protocol = "ipv6"

    def get_check_results(self, timeout):
        if not hasattr(self, "process"):
            return CheckResult.UNRESOLVABLE
        
        try:
            self.process.wait(timeout=timeout)
        except TimeoutExpired:
            print("%s timed out" % self.name)
            self.process.kill()
            return CheckResult.UNREACHABLE

        unroutable_ip = False
        if not self.used_address.is_global and not self.non_global_okay:
            unroutable_ip = True

        for line in self.process.stdout:
            if b"packets transmitted" in line:
                match = ping_summary_regex.search(line.decode(encoding="ascii"))
                self.sent = int(match.group(1))
                self.received = int(match.group(2))
                self.packet_loss = int(match.group(3))
                if unroutable_ip:
                    return CheckResult.UNROUTABLE_IP
                elif self.received == self.sent:
                    return CheckResult.OK
                elif self.received > 0:
                    return CheckResult.PACKET_LOSS
                else:
                    return CheckResult.UNREACHABLE

        return CheckResult.UNKNOWN # Only reached if we did not see a ping summary line

def get_configuration(paths):
    configuration = ConfigParser()
    configuration_read = False
    paths_iter = iter(paths)
    while not configuration_read:
        try:
            with open(next(paths_iter), "r") as file:
                configuration.read_file(file)
                configuration_read = True
        except FileNotFoundError:
            pass
    return configuration

if __name__ == '__main__':
    configuration = get_configuration([
        "connectivity_logger.cfg",
        os.path.expanduser("~/.connectivity_logger.cfg"),
        "/etc/connectivity_logger.cfg",
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "connectivity_logger.cfg")]
        )

    # We assume this script will be run once per minute, so we set ourselves a deadline
    # for all checks for 45 seconds from now. This should give us enough time to finish
    # up before the next start.
    # TODO Also use a file lock
    deadline = time.time() + 45
    check_time = datetime.now(tz=timezone.utc)

    num_pings = configuration["connectivity_logger"].getint("pings", 5)
    ping_interval = configuration["connectivity_logger"].getfloat("ping_interval", 1.0)

    ping_checks = []
    for section in configuration:
        if section not in ['DEFAULT', 'connectivity_logger']:
            if configuration[section].get("protocol", "any") == "both":
                ping_check_v4 = PingCheck(section, configuration[section],
                                          num_pings=num_pings,
                                          interval=ping_interval)
                ping_check_v4.protocol = "ipv4"
                ping_check_v4.start_check()
                ping_checks.append(ping_check_v4)
                ping_check_v6 = PingCheck(section, configuration[section],
                                          num_pings=num_pings,
                                          interval=ping_interval)
                ping_check_v6.protocol = "ipv6"
                ping_check_v6.start_check()
                ping_checks.append(ping_check_v6)
            else:
                ping_check = PingCheck(section, configuration[section],
                                       num_pings=num_pings,
                                       interval=ping_interval)
                ping_check.start_check()
                ping_checks.append(ping_check)
    
    with open(configuration["connectivity_logger"].get("logfile", "connectivity_log.csv"), "a") as logfile:
        for ping_check in ping_checks:
            result = ping_check.get_check_results(timeout=deadline - time.time())
            logfile.write("{};{};{};{};{};{};{}\n".format(
                check_time.strftime("%Y-%m-%d %H:%M UTC"),
                ping_check.name, # TODO Escape name for CSV format
                ping_check.used_protocol,
                ping_check.used_address,
                result.name,
                getattr(ping_check, "sent", ""),
                getattr(ping_check, "received", "")))
