## [FacetimeHD](https://github.com/patjak/bcwc_pcie)(Broadcom 1570) driver

#### AUR package

There is [AUR package](https://aur.archlinux.org/packages/bcwc-pcie-git/) available, and another one for the firmware itself (the separation will make upgrades less painful, and don't force you to keep firmware.bin around forever).

#### Build from source

If you want to install the kernel module manually, instead, you should:

1. Extract firmware file as described in [Firmware extraction](https://github.com/patjak/bcwc_pcie/wiki/Get-Started#firmware-extraction).
1. Install dependencies: `sudo pacman -S linux-headers git kmod`
1. Clone driver's code: `git clone https://github.com/patjak/bcwc_pcie.git`
1. Step into cloned dir: `cd bcwc_pcie`
1. Build kernel module: `make`
1. Install kernel module: `sudo make install`
1. Run depmod for kernel to be able to find and load it: `sudo depmod`
1. Load kernel module: `sudo modprobe facetimehd`
1. Try it with the application of choice. mpv for example: `sudo pacman -S mpv && mpv tv://`

#### More info [here](https://github.com/patjak/bcwc_pcie/wiki/Get-Started).
