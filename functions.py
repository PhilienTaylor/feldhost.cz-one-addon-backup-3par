def bool_arg(string):
    if string != True and string != '1' and string != 'YES':
        return False
    return True


def list_of_int_arg(string):
    return map(int, string.split(','))


def list_arg(string):
    return string.split(',')


def get_vm_hostname(vm):
    if isinstance(vm.HISTORY_RECORDS.HISTORY, list):
        return vm.HISTORY_RECORDS.HISTORY.pop().HOSTNAME

    return vm.HISTORY_RECORDS.HISTORY.HOSTNAME
