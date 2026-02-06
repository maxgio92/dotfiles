.PHONY: all
all: base docker

.PHONY: base
base:
	rpm-ostree install \
		clang \
		elfutils-libelf-devel \
		libbpf-devel \
		zlib-devel \
		kernel-devel \
		qemu \
		alacritty

.PHONY: docker
docker: docker-repo
	rpm-ostree install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

.PHONY: docker-repo
docker-repo:
	curl -O https://download.docker.com/linux/fedora/docker-ce.repo
	sudo install -o 0 -g 0 -m644 docker-ce.repo /etc/yum.repos.d/docker-ce.repo

