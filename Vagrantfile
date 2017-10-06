# -*- mode: ruby -*-
# vi: set ft=ruby :

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  config.vm.box = "ubuntu/trusty64"
  config.vm.hostname = "history-server-dev-vm"

  # this box has libvirt capabilities.
  config.vm.provider "libvirt" do |v, override|
    override.vm.box = "baremettle/ubuntu-14.04"
  end
  config.vm.provider "lxc" do |v, override|
    override.vm.box = "fgrehm/trusty64-lxc"
  end

  config.vm.provision "shell", inline: "apt-get update"
  config.vm.provision "shell", inline: "apt-get -y install puppet"

  # pick up the aws keys as shared, if they exist.
  if File.exist?(File.expand_path("~/.aws")) then
    config.vm.synced_folder "~/.aws", "/home/vagrant/.aws"
  end

  # pick up the local bindir, if it exists
  if File.directory?(File.expand_path("~/bin"))
    config.vm.synced_folder "~/bin", "/home/vagrant/bin"
  end
  # provision dotfiles out of host homedir when they exist
  dotfiles = %w{ gitconfig gitignore
                 profile login logout }
  dotfiles.each do |dotfile|
    dotfile_full = File.expand_path("~/.#{dotfile}")
    if File.exists?(dotfile_full)
      config.vm.provision "file", source: dotfile_full, destination: "/home/vagrant/.#{dotfile}"
    end
  end

  # append some ease-of-use env vars to the login.
  config.vm.provision "shell", inline: "echo '. /vagrant/vagrant/scripts/startup.sh' >> /home/vagrant/.bashrc"

  # our environment is "workstation", it would default to "production"
  # otherwise, which is panic-inducing!
  config.vm.provision "puppet",  :options => ["--environment", "workstation"] do |puppet|
    puppet.manifests_path = "vagrant/manifests"
    puppet.manifest_file  = "default.pp"
  end

end
