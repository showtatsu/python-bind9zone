from setuptools import setup, find_packages

def _req_from_file(filename):
    return open(filename).read().strip().splitlines()

setup(name="bind9zone",
        version="0.1.5",
        description="BIND9 zonedata manager for platform island.",
        author="Tatsuya SHORIKI",
        author_email="show.tatsu.devel@gmail.com",
        classifiers=[
            'Development Status :: 3 - Alpha',
            'License :: OSI Approved :: MIT License',
            'Intended Audience :: System Administrators',
            'Programming Language :: Python :: 3',
            'Natural Language :: Japanese',
        ],
        packages=find_packages(),
        install_requires=['psycopg2-binary' ,'sqlalchemy', 'validators'],
        extras_require={
            'test': ['pytest', 'pytest-cov', 'coverage[toml]'],
        },
        entry_points={"console_scripts": [
            "bind9zone = bind9zone.cli:main"
        ]},
    )
