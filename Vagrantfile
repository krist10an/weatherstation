$bootstrap = <<SCRIPT
date > /etc/vagrant_provisioned_at

apt-get update
apt-get install -y ansible

mkdir -p /etc/ansible/
cp /vagrant/ansible_inventory /etc/ansible/hosts
SCRIPT

$provision = <<SCRIPT
export PYTHONUNBUFFERED=1
export ANSIBLE_FORCE_COLOR=1
ansible-playbook /vagrant/playbooks/site.yml
SCRIPT

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/trusty64"

  config.vm.provision "shell", inline: $bootstrap
  config.vm.provision "shell", inline: $provision, privileged: false
end
