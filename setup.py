from setuptools import setup

setup(
    name='profitbot',
    version='0.0.5',
    packages=['profitbot'],
    description='Trans Fee Miner Bot for BitMax.io Exchange',
    url='https://github.com/electromind/profitbot_v2',
    author='electromind',
    license='MIT',
    author_email='electromind.work@gmail.com',
    install_requires=['requests', 'termcolor'],
    keywords='bitmax exchange rest api fee mining usdt usdc xrp bitcoin ethereum btc eth neo',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)