import os

IP_SCRIPT_DIR = "RasPi-DIDComm-weather-monitoring"


def get_agent_endpoint():
    agent_endpoint = ""
    if os.popen("uname").read().strip() == "Darwin":
        # determine if we need to go back to find the script
        wd = os.popen("pwd").read().strip().split("/")
        proj_i = 0
        for i in range(len(wd)):
            if wd[i] == IP_SCRIPT_DIR:
                proj_i = i
                break
        back = len(wd) - proj_i - 1

        # run the script
        if back == 0:
            agent_endpoint = os.popen("chmod +x ./macOS_get_ip.sh && ./macOS_get_ip.sh").read().strip()
        else:
            command = "chmod +x " + (back * "../") + "macOS_get_ip.sh && " + (back * "../") + "macOS_get_ip.sh"
            agent_endpoint = os.popen(command).read().strip()

    elif os.popen("uname").read().strip() == "Linux":
        agent_endpoint = os.popen("ip route get 8.8.8.8 | grep -oP 'src \\K[^ ]+'").read().strip()

    return agent_endpoint
