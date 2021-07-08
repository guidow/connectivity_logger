# Internet Connectivity Logger
A simple logging tool to get some data on the reliability of your internet connection.

This tool is intended to be run as a cron job once per minute.

## Platforms
Currently only tested under Linux. Will likely also work under *BSD and MacOS. Will
probably not work under Windows.

This tool uses the platform's `ping` utility and relies on the specific output format to
get its results. I briefly considered doing the ping directly from the python script,
but that would require running the script as root or giving it `RAW_SOCKET`
capabilities. The former is completely inadvisable, and the latter turned out to be
much more involved than I anticipated. I might come back to that possibility later
still.

## Configuration
The script requires a configuration file to run. An example configuration that will
probably work as is for most people has been provided.

The configuration file will be looked for in the following places, in that order:

- The current working directory as `connectivity_logger.cfg`
- The current user's home directory as `.connectivity_logger.cfg`
- `/etc/connectivity_logger.cfg`
- The directory of the script itself as `connectivity_logger.cfg`

Only the first configuration file found will be read. The others will be ignored.

Since there is an example configuration file in the repository right next to the script,
just running it from the checked out git working directory will work for most. However,
if you want to make changes to the configuration file, you should first copy the file to
one of those other locations.

## Installation
As long as you already have Python itself installed and running, this script itself will
require no special installation procedure. Just put it somewhere on your disk where you
like it and run it from there.

To make the most of it, it should be configured as a cronjob, though. Run `crontab -e`
and add the following line somewhere:

    * * * * * <path/to/connectivity_logger.py>

Replacing `<path/to/connectivity_logger.py>` with the actual, correct path, of course.

## Checks
The only checks currently supported are ping via IPv4 and/or IPv6. HTTPS connection tests
are planned for the future.

Some home routers have the nasty habit of faking DNS answers in the case of an outage
to point them to themselves instead. This allows them to show the user an error page
instead of the site they were actually trying to visit, but obviously interferes with
our checks. For this reason, we resolve the IP addresses we ping manually (instead of
letting the `ping` utility do that for us) and both log the used addresses and check
whether they are actually globally routable.

## Output
The results of the checks are collected in a simple CSV file, suitable for viewing in a
spreadsheet application.

The CSV can become quite large with time, which may overwhelm some spreadsheet software.
An auto-rotation feature is planned to avoid that.

Another script to get some statistics from that data is planned for the future.
