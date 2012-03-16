#!/usr/bin/env python

def password_reset(args):
    print " [*] We do reset passowrd for specific user"

def new_user(args):
    print " [*] We do generate new user"

def unsupported_commands():
    print " [*] sorry, currently this command is not supported"

def exec_command(command_name, is_admin, command_args):
    if (command_name == 'password_reset' and is_admin == 'True'):
        password_reset(command_args)
    elif (command_name == 'new_user' and is_admin == 'True'):
        new_user(command_args)
    else:
        unsupported_commands
