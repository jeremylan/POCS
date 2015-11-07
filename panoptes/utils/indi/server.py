import os
import shutil
import subprocess

from .. import has_logger
from .. import error


@has_logger
class PanIndiServer(object):

    """ A module to start an INDI server

    Args:
        drivers(dict):  Dict of valid drivers for indiserver to start, defaults to
            {'PAN_CCD_SIMULATOR': 'indi_simulator_ccd'}
        fifo(str):      Path to FIFO file of running indiserver
    """

    def __init__(self, fifo='/tmp/pan_indiFIFO'):
        self._indiserver = shutil.which('indiserver')

        assert self._indiserver is not None, error.PanError("Cannot find indiserver command")

        # Start the server
        self._fifo = fifo

        try:
            self._proc = self.start()
        except Exception as e:
            self.logger.warning("Problem with staring the INDI server: {}".format(e))

        self._connected = False
        self.logger.debug("PanIndiServer created. PID: {}".format(self._proc))


##################################################################################################
# Properties
##################################################################################################

    @property
    def is_connected(self):
        """ INDI Server connection

        Tests whether running PID exists
        """
        try:
            self._connected = os.path.exists('/proc/{}'.format(self._proc.pid))
        except Exception:
            self.logger.warning("Error checking for PID {}".format(self._proc.pid))

        return self._connected

##################################################################################################
# Methods
##################################################################################################

    def start(self, *args, **kwargs):
        """ Start an INDI server.

        Host, port, and drivers must be configured in advance.

        Returns:
            _proc(process):     Returns process from `subprocess.Popen`
        """

        try:
            if not os.path.exists(self._fifo):
                os.mkfifo(self._fifo)
            else:
                self.logger.warning('FIFO already exists.')

        except Exception as e:
            raise error.InvalidCommand("Can't open fifo at {} \t {}".format(self._fifo, e))

        cmd = [self._indiserver]

        opts = args if args else ['-m', '100', '-f', self._fifo]
        cmd.extend(opts)

        try:
            self.logger.debug("Starting INDI Server: {}".format(cmd))
            proc = subprocess.Popen(cmd, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            self.logger.debug("INDI server started. PID: {}".format(proc.pid))
        except Exception as e:
            self.logger.warning("Cannot start indiserver on {}:{}. {}".format(self.host, self.port, e))

        return proc

    def stop(self):
        """ Stops the INDI server """
        if os.getpgid(self._proc.pid):
            self.logger.debug("Shutting down INDI server (PID {})".format(self._proc.pid))
            self._proc.terminate()

        if os.path.exists(self._fifo):
            os.unlink(self._fifo)

    def load_drivers(self, devices={}):
        """ Load all the device drivers

        Args:
            devices(list):      A list of PanIndiDevice objects
        """
        # Load the drivers
        for dev_name, dev_driver in devices.items():
            try:
                self.load_driver(dev_name, dev_driver)
            except error.InvalidCommand:
                self.logger.warning(
                    "Problem loading {} ({}) driver. Skipping for now.".format(dev_name, dev_driver))

    def load_device_driver(self, device):
        """ Convenince method that load the driver for given device """
        self.load_driver(device.name, device.driver)

    def load_driver(self, name, driver):
        """ Loads a driver into the running server """
        self.logger.debug("Loading driver".format(driver))

        cmd = ['start', driver]

        if name:
            cmd.extend(['-n', '\"{}\"'.format(name), '\n'])

        self._write_to_server(cmd)

    def unload_driver(self, name, driver):
        """ Unloads a driver from the server """
        self.logger.debug("Unloading driver".format(driver))

        # Need the explicit quotes below
        cmd = ['stop', driver, '\"{}\"'.format(name), '\n']

        self._write_to_server(cmd)

##################################################################################################
# Private Methods
##################################################################################################

    def _write_to_server(self, cmd):
        """ Write the command to the FIFO server """
        assert self._proc.pid, error.InvalidCommand("No running server found")
        assert self._fifo, error.InvalidCommand("No FIFO file found")

        str_cmd = ' '.join(cmd)
        self.logger.debug("Command to FIFO server: {}".format(str_cmd))
        try:
            # I can't seem to get the FIFO to work without the explicit flush and close
            with open(self._fifo, 'w') as f:
                f.write(str_cmd)
                f.flush()
                f.close()
        except Exception as e:
            raise error.PanError("Problem writing to FIFO: {}".format(e))

    def __del__(self):
        self.stop()
