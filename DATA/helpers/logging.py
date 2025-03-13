from colorama import Fore, Back, Style
import traceback, datetime


class _LOGGING:
    """
    Logging colors
    """

    class cowolors:
        def __init__(self):
            # Reset all styles
            self.reset = Style.RESET_ALL
            # Timestamp
            self.timestamp = f"{Style.BRIGHT}{Fore.LIGHTBLACK_EX}"
            # Normal message text
            self.normal_message = Fore.WHITE

            # [TWITCH]
            self.twitch_logs = Fore.MAGENTA
            # [INFO]
            self.info_logs = Fore.CYAN
            # [COGS]
            self.cog_logs = Fore.BLUE
            # [COMMAND]
            self.command_logs = Fore.BLUE
            # [SUCCESS]
            self.success_logs = Fore.LIGHTGREEN_EX
            # [ERROR]
            self.error_logs = Fore.RED
            # [WARN]
            self.warn_logs = "\033[38;2;255;165;0m"  # This is orange!

            # Normal item names (inputted text from user usually is an item)
            self.item_name = Fore.LIGHTBLUE_EX
            # A user's name
            self.user_name = Fore.LIGHTCYAN_EX

    COLORS = cowolors()

    def print(self, *args, **kwargs):
        timestamp = f"{self.COLORS.timestamp}[{datetime.datetime.now(datetime.timezone.utc).strftime('%Y/%m/%d %H:%M:%S.%f')[:-3]} UTC]{self.COLORS.reset}"
        if args:
            args = (timestamp + " " + str(args[0]),) + args[1:]
        else:
            args = (timestamp,)
        print(*args, **kwargs)

    def infoprint(self, *args, **kwargs):
        if args:
            args = (
                f"{self.COLORS.info_logs}[INFO]{self.COLORS.normal_message}"
                + " "
                + str(args[0]),
            ) + args[1:]
        else:
            args = (f"{self.COLORS.info_logs}[INFO]{self.COLORS.normal_message}",)
        self.print(*args, **kwargs)

    def warnprint(self, *args, **kwargs):
        if args:
            args = (
                f"{self.COLORS.warn_logs}[WARN]{self.COLORS.normal_message}"
                + " "
                + str(args[0]),
            ) + args[1:]
        else:
            args = (f"{self.COLORS.warn_logs}[WARN]{self.COLORS.normal_message}",)
        self.print(*args, **kwargs)

    def errorprint(self, *args, **kwargs):
        if args:
            args = (
                f"{self.COLORS.error_logs}[ERROR]{self.COLORS.normal_message}"
                + " "
                + str(args[0]),
            ) + args[1:]
        else:
            args = (f"{self.COLORS.error_logs}[ERROR]{self.COLORS.normal_message}",)
        self.print(*args, **kwargs)

    def successprint(self, *args, **kwargs):
        if args:
            args = (
                f"{self.COLORS.success_logs}[SUCCESS]{self.COLORS.normal_message}"
                + " "
                + str(args[0]),
            ) + args[1:]
        else:
            args = (f"{self.COLORS.success_logs}[SUCCESS]{self.COLORS.normal_message}",)
        self.print(*args, **kwargs)

    def tracebackprint(self, error: Exception):
        separator_line = "-" * 60

        traceback_lines = traceback.format_exception(error, error, error.__traceback__)

        print(separator_line)

        errortimestamp = (
            datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y/%m/%d %H:%M:%S.%f"
            )[:-3]
            + " UTC"
        )

        for line in traceback_lines:
            for subline in line.split("\n"):
                self.print(
                    f"{self.COLORS.timestamp}[{errortimestamp}]{self.COLORS.reset} {self.COLORS.error_logs}[ERROR]{self.COLORS.normal_message} {subline}"
                )

        print(separator_line)


LOGGING = _LOGGING()
