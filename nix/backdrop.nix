# syncrain backdrop as a NixOS flavour: KDE Plasma 6 on Wayland with the rain as the wallpaper, the
# login screen and the lock screen. Boot stays plain text (NixOS has no Plymouth unless asked): the
# text says the machine is not up yet, the rain that it is. Every setting here is a default, so a
# configuration that imports this says otherwise where it wants.
{ lib, ... }:
{
  services.desktopManager.plasma6.enable = lib.mkDefault true;
  services.displayManager.sddm.enable = lib.mkDefault false;     # syncrain's login screen instead

  services.syncrain = {
    enable = lib.mkDefault true;
    loginScreen.enable = lib.mkDefault true;
    lockScreen.enable = lib.mkDefault true;
  };

  # what a desktop needs that Plasma does not bring: a network, sound, the clock in sync (the
  # rain is a function of it)
  networking.networkmanager.enable = lib.mkDefault true;
  services.pipewire = { enable = lib.mkDefault true; pulse.enable = lib.mkDefault true; };
  services.timesyncd.enable = lib.mkDefault true;
}
