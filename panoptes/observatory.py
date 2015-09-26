import os
import datetime
import importlib

import astropy.units as u
from astropy.time import Time
from astropy.coordinates import EarthLocation

from . import mount as mount
from . import camera as camera
from .scheduler import Scheduler, SchedulerSimple

from .utils import *

@has_logger
class Observatory(Observer):

    """
    Main Observatory class
    """

    def __init__(self, config=None, *args, **kwargs):
        """
        Starts up the observatory. Reads config file (TODO), sets up location,
        dates, mount, cameras, and weather station
        """
        assert config is not None, self.logger.warning( "Config not set for observatory")
        self.config = config

        self.logger.info('Initializing observatory')

       # Setup information about site location
        self.logger.info('\t Setting up observatory details')
        self.location = {}
        self._setup_location()

        self.mount = None
        self.cameras = list()
        self.scheduler = None

        self._create_mount()
        self._create_cameras()
        self._create_scheduler()

##################################################################################################
# Methods
##################################################################################################

    def get_target(self):
        """ Gets the next target from the scheduler """

        self.logger.debug("Getting target for observatory")
        target = self.scheduler.get_target(self)
        self.logger.debug("Got target for observatory: {}".format(target))

        return target

##################################################################################################
# Private Methods
##################################################################################################

    def _setup_location(self):
        """
        Sets up the site and location details for the observatory

        Note:
            These items are read from the 'site' config directive and include:
                * name
                * latitude
                * longitude
                * timezone
                * presseure
                * elevation
                * horizon

        """
        self.logger.info('Setting up site details of observatory')

        if 'location' in self.config:
            config_site = self.config.get('location')

            name = config_site.get('name', 'Nameless Location')

            latitude = config_site.get('latitude') * u.degree
            longitude = config_site.get('longitude') * u.degree

            timezone = config_site.get('timezone')

            pressure = config_site.get('pressure', 0.680) * u.bar
            elevation = config_site.get('elevation', 0) * u.meter
            horizon = config_site.get('horizon', 0) * u.degree

            self.location = {
                'name': name,
                'latitude': latitude,
                'longitude': longitude,
                'elevation': elevation,
                'timezone': timezone,
                'pressure': pressure,
                'horizon': horizon
            }
            self.logger.debug("location set: {}".format(self.location))
        else:
            raise error.Error(msg='Bad site information')

    def _create_mount(self, mount_info=None):
        """Creates a mount object.

        Details for the creation of the mount object are held in the
        configuration file or can be passed to the method.

        This method ensures that the proper mount type is loaded.

        Note:
            This does not actually make a serial connection to the mount. To do so,
            call the 'mount.connect()' explicitly.

        Args:
            mount_info (dict):  Configuration items for the mount.

        Returns:
            panoptes.mount:     Returns a sub-class of the mount type
        """
        if mount_info is None:
            mount_info = self.config.get('mount')

        model = mount_info.get('model')

        self.logger.info('Creating mount: {}'.format(model))

        mount = None

        module = load_module('panoptes.mount.{}'.format(model))

        # Make the mount include site information
        self.mount = module.Mount(config=self.config, location=self.location)
        self.logger.info('Mount created')

    def _create_cameras(self, camera_info=None):
        """Creates a camera object(s)

        Creates a camera for each camera item listed in the config. Ensures the
        appropriate camera module is loaded.

        Note:
            This does not actually make a usb connection to the camera. To do so,
            call the 'camear.connect()' explicitly.

        Args:
            camera_info (dict): Configuration items for the cameras.

        Returns:
            list: A list of created camera objects.
        """
        camera_info = self.config.get('cameras')
        if camera_info is None:
            camera_info = self.config.get('mount')


        self.logger.debug("Camera config: \n {}".format(camera_info))

        cameras = list()

        for camera in camera_info:
            # Actually import the model of camera
            camera_model = camera.get('model')

            self.logger.info('Creating camera: {}'.format(camera_model))

            try:
                module = load_module('panoptes.camera.{}'.format(camera_model))
                cameras.append(module.Camera(config=camera))

            except ImportError as err:
                raise error.NotFound(msg=camera_model)

        self.cameras = cameras
        self.logger.info("Cameras created.")

    def _create_scheduler(self):
        """ Sets up the scheduler that will be used by the observatory """

        # Read the targets from the file
        targets_path = os.path.join(
            self.config.get('base_dir'),
            'resources/conf_files/targets/',
            self.config.get('targets_file')
        )

        if os.path.exists(targets_path):
            self.logger.info('Creating scheduler: {}'.format(targets_path))
            self.scheduler = Scheduler(target_list_file=targets_path, location=self.location)
            self.logger.info("Scheduler created")
        else:
            self.logger.warning("Targets file does not exist: {}".format(targets_path))
