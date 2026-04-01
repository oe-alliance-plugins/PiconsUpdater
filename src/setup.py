from setuptools import setup
import setup_translate

pkg = 'Extensions.PiconsUpdater'
setup(name='enigma2-plugin-extensions-piconsupdater',
       version='3.0',
       description='Download and install new Picons for your current bouquet channels. PiconsUpdater coded by svox and jbleyel, idea by arn354 and picons by mike99',
       package_dir={pkg: 'PiconsUpdater'},
       packages=[pkg],
       package_data={pkg: ['images/*.png', '*.png', '*.xml', 'locale/*/LC_MESSAGES/*.mo', 'plugin.png']},
       cmdclass=setup_translate.cmdclass,  # for translation
      )
