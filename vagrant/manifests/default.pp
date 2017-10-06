exec { "update python dev":
  command => "apt-get install -y python-dev",
  path => "/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin" }

# psycopg2 requires pg_config from libpq-dev
package { "libpq-dev": ensure => "latest"}

# Helpfulness
package { "git": ensure => "latest"}

# PIP
package { "python-pip": ensure => "latest"}

exec { "install requirements.txt":
  command => "pip install -r /vagrant/src/requirements.txt",
  path => "/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin",
  require => [Package['python-pip']] }



# postgres goop
# wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
# deb http://apt.postgresql.org/pub/repos/apt/ trusty-pgdg main
# sudo apt-get install -yy postgresql-9.4 postgresql-9.4-dbg postgresql-client-9.4postgresql-doc-9.4  postgresql-server-dev-9.4
