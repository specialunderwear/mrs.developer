from mrs.developer.base import Cmd
from mrs.developer.base import logger
import base64
import re
import urllib
import urllib2


class Reload(Cmd):
    """Reload code while zope instance is running using `plone.reload`.
    """

    def __call__(self, dists=None, pargs=None):
        if not self.root:
            logger.error("Not rooted, run 'mrsd init'.")
            return

        http_headers = {}
        http_data = {}

        # the action is either "code" or "zcml", but the zcml also reloads
        # the code...
        http_data['action'] = pargs.zcml and 'zcml' or 'code'

        # generate the ac_value cookie for authentication
        ac_value = ':'.join((pargs.username.encode('hex'),
                             pargs.password.encode('hex')))
        ac_value = str(base64.encodestring(ac_value)).strip()
        http_headers['Cookie'] = '__ac=%s' % ac_value

        # prepare the url
        url = 'http://%s:%s/@@reload' % (pargs.host, pargs.port)

        # make the request
        request = urllib2.Request(url, urllib.urlencode(http_data),
                                  http_headers)
        try:
            response = urllib2.urlopen(request)
        except urllib2.URLError, e:
            if getattr(e, 'code', '') == 404:
                return {'status': str(e),
                    'success': False,
                        'help': 'It seems that plone.reload is not installed '
                        'on your zope installation. Add plone.reload to your '
                        'eggs in the instance-section of your buildout.cfg '
                        'and re-run bin/buildout.'}
            else:
                return {'status': str(e),
                    'success': False}

        html = response.read()

        # parse response
        xpr = re.compile('<pre.*?>(.*?)</pre>', re.DOTALL)
        match = xpr.search(html)

        if match:
            # success
            result = {}
            resp_lines = match.groups()[0].split('\n')
            result['status'] = '\n'.join(resp_lines[:1]).strip()
            result['success'] = True
            if len(resp_lines)>1:
                result['files'] = resp_lines[2:]
            return result

        else:
            # failed
            return {'status': html,
                    'success': False}

    def _initialize(self):
        """Initializes the mrsd configuration
        """

        if not self.cfg.get('reload'):
            self.cfg.setdefault('reload', {'instances': []})

    def _defaults(self):
        """Returns a dict of some default values for arguments.
        The default values are guessed from the buildout configuration, if
        mrs.developer is defined as extension and buildout was executed.
        """

        defaults = {'username': 'admin',
                    'password': 'admin',
                    'port': 8080,
                    'host': 'localhost'}

        if self.cfg.get('reload', {}).get('instances'):
            instances = self.cfg['reload']['instances']
            if len(instances) == 1:
                defaults = instances[0].copy()

        return defaults

    def init_argparser(self, parser):
        """Add our arguments to a parser
        """

        defaults = self._defaults()

        parser.add_argument(
            '--zcml',
            dest='zcml',
            action='store_true',
            default=False,
            help='Reload ZCML too.')

        parser.add_argument(
            '--user',
            dest='username',
            action='store',
            default=defaults['username'],
            help='Zope-Username for logging into ZMI')

        parser.add_argument(
            '--pass',
            dest='password',
            action='store',
            default=defaults['password'],
            help='Password of Zope-User (--user)')

        parser.add_argument(
            '--host',
            dest='host',
            action='store',
            default=defaults['host'],
            help='Hostname where zope is running at')

        parser.add_argument(
            '--port',
            dest='port',
            action='store',
            default=defaults['port'],
            help='Port where zope is running at')

    def _configure(self, buildout):
        """Called by the unload extension if mrsd.developer is defined in
        the extension of the buildout.
        This method looks up instance parts in buildout and stores host,
        port, username and password in the mrsd config file, which is then
        used as default values.
        """

        self.cfg['reload']['instances'] = []

        for partname, part in buildout.items():
            inst = {}
            if part.get('recipe') == 'plone.recipe.zope2instance':
                # we have a zope instance

                # ... port
                try:
                    inst['port'] = int(part.get('http-address', 8080))
                except ValueError:
                    continue
                else:
                    if part.get('port-base'):
                        try:
                            inst['port'] += int(part.get('port-base'))
                        except ValueError:
                            continue

                # ip / host
                inst['host'] = part.get('ip-address', '0.0.0.0')

                # user
                user = part.get('user', 'admin:admin')
                inst['username'] = user.split(':', 1)[0]
                inst['password'] = user.split(':', 1)[1]

                # name
                inst['name'] = partname

            elif part.get('recipe') == 'collective.recipe.zope2cluster':
                # we have a clustered zeo instance, which is copied from
                # "instance-clone"
                logger.log('zope2cluster not supported yet')

            if inst:
                self.cfg['reload']['instances'].append(inst)

        self.cmds.save_config()
