## Setting up wifi cards

Check if wfifi is blocked by rfkill

```bash
rfkill list
# If it is blocked:
sudo rfkill unblock wifi
```

Then enable the wifi:


```bash
nmcli radio wifi on
```