#!/usr/bin/env python
import PySimpleGUI as sg
import psutil
import sqlite3

GRAPH_WIDTH, GRAPH_HEIGHT = 120, 40
ALPHA = .7

class DashGraph(object):
    def __init__(self, graph_elem, starting_count, color):
        self.graph_current_item = 0
        self.graph_elem = graph_elem
        self.prev_value = starting_count
        self.max_value = starting_count
        self.min_value = starting_count
        self.color = color
        self.graph_lines = []

    def graph_value(self, current_value):
        delta = current_value - self.prev_value
        self.prev_value = current_value
        self.max_value = max(self.max_value, current_value)
        self.min_value = min(self.min_value, current_value)
        percent_sent = 100 * delta / (self.max_value - self.min_value + 1)
        line_id = self.graph_elem.draw_line((self.graph_current_item, 0), (self.graph_current_item, percent_sent), color=self.color)
        self.graph_lines.append(line_id)
        if self.graph_current_item >= GRAPH_WIDTH:
            self.graph_elem.delete_figure(self.graph_lines.pop(0))
            self.graph_elem.move(-1, 0)
        else:
            self.graph_current_item += 1
        return delta

    def graph_percentage_abs(self, value):
        percent_value = 100 * (value - self.min_value) / (self.max_value - self.min_value + 1)
        self.graph_elem.draw_line((self.graph_current_item, 0), (self.graph_current_item, percent_value), color=self.color)
        if self.graph_current_item >= GRAPH_WIDTH:
            self.graph_elem.move(-1, 0)
        else:
            self.graph_current_item += 1

def create_database():
    conn = sqlite3.connect('dashboard_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dashboard_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            net_out INTEGER,
            net_in INTEGER,
            disk_read INTEGER,
            disk_write INTEGER,
            cpu_usage INTEGER,
            mem_usage INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def insert_data_to_database(data):
    conn = sqlite3.connect('dashboard_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO dashboard_data (net_out, net_in, disk_read, disk_write, cpu_usage, mem_usage)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', data)
    conn.commit()
    conn.close()

def main():
    create_database()

    sg.theme('Black')
    sg.set_options(element_padding=(0, 0), margins=(1, 1), border_width=0)
    location = sg.user_settings_get_entry('-location-', (None, None))

    def GraphColumn(name, key, min_key, max_key):
        layout = [
            [sg.Text(name, size=(18, 1), font=('Helvetica 8'), key=key + 'TXT_')],
            [sg.Graph((GRAPH_WIDTH, GRAPH_HEIGHT),
                      (0, 0),
                      (GRAPH_WIDTH, 100),
                      background_color='black',
                      key=key + 'GRAPH_')],
            [sg.Text('Min: ', key=min_key), sg.Text('Max: ', key=max_key)]
        ]
        return sg.Col(layout, pad=(2, 2))

    layout = [
        [sg.Text('System Status Dashboard' + ' ' * 18)],
        [GraphColumn('Net Out', '_NET_OUT_', '_MIN_NET_OUT_', '_MAX_NET_OUT_'),
         GraphColumn('Net In', '_NET_IN_', '_MIN_NET_IN_', '_MAX_NET_IN_')],
        [GraphColumn('Disk Read', '_DISK_READ_', '_MIN_DISK_READ_', '_MAX_DISK_READ_'),
         GraphColumn('Disk Write', '_DISK_WRITE_', '_MIN_DISK_WRITE_', '_MAX_DISK_WRITE_')],
        [GraphColumn('CPU Usage', '_CPU_', '_MIN_CPU_', '_MAX_CPU_'),
         GraphColumn('Memory Usage', '_MEM_', '_MIN_MEM_', '_MAX_MEM_')],
    ]

    window = sg.Window('PSG System Dashboard', layout,
                       keep_on_top=True, grab_anywhere=True, no_titlebar=True,
                       return_keyboard_events=True, alpha_channel=ALPHA,
                       enable_close_attempted_event=True, use_default_focus=False,
                       finalize=True, location=location,
                       right_click_menu=sg.MENU_RIGHT_CLICK_EDITME_VER_EXIT)

    netio = psutil.net_io_counters()
    net_in = window['_NET_IN_GRAPH_']
    net_graph_in = DashGraph(net_in, netio.bytes_recv, '#23a0a0')
    net_out = window['_NET_OUT_GRAPH_']
    net_graph_out = DashGraph(net_out, netio.bytes_sent, '#56d856')

    diskio = psutil.disk_io_counters()
    disk_graph_write = DashGraph(window['_DISK_WRITE_GRAPH_'], diskio.write_bytes, '#be45be')
    disk_graph_read = DashGraph(window['_DISK_READ_GRAPH_'], diskio.read_bytes, '#5681d8')

    cpu_usage_graph = DashGraph(window['_CPU_GRAPH_'], 0, '#d34545')
    mem_usage_graph = DashGraph(window['_MEM_GRAPH_'], 0, '#BE7C29')

    while True:
        event, values = window.read(timeout=1000)
        if event in (sg.WIN_CLOSE_ATTEMPTED_EVENT, 'Exit'):
            sg.user_settings_set_entry('-location-', window.current_location())
            break

        netio = psutil.net_io_counters()
        write_bytes = net_graph_out.graph_value(netio.bytes_sent)
        read_bytes = net_graph_in.graph_value(netio.bytes_recv)

        insert_data_to_database((write_bytes, read_bytes, 0, 0, 0, 0))

        diskio = psutil.disk_io_counters()
        write_bytes = disk_graph_write.graph_value(diskio.write_bytes)
        read_bytes = disk_graph_read.graph_value(diskio.read_bytes)

        insert_data_to_database((0, 0, read_bytes, write_bytes, 0, 0))

        cpu = psutil.cpu_percent(0)
        cpu_usage_graph.graph_percentage_abs(cpu)

        insert_data_to_database((0, 0, 0, 0, cpu, 0))

        mem_used = psutil.virtual_memory().percent
        mem_usage_graph.graph_percentage_abs(mem_used)

        insert_data_to_database((0, 0, 0, 0, 0, mem_used))

        # Обновляем текстовые элементы с минимальными и максимальными значениями
        window['_MIN_NET_OUT_'].update('Min: {}'.format(net_graph_out.min_value))
        window['_MAX_NET_OUT_'].update('Max: {}'.format(net_graph_out.max_value))
        window['_MIN_NET_IN_'].update('Min: {}'.format(net_graph_in.min_value))
        window['_MAX_NET_IN_'].update('Max: {}'.format(net_graph_in.max_value))
        window['_MIN_DISK_READ_'].update('Min: {}'.format(disk_graph_read.min_value))
        window['_MAX_DISK_READ_'].update('Max: {}'.format(disk_graph_read.max_value))
        window['_MIN_DISK_WRITE_'].update('Min: {}'.format(disk_graph_write.min_value))
        window['_MAX_DISK_WRITE_'].update('Max: {}'.format(disk_graph_write.max_value))
        window['_MIN_CPU_'].update('Min: {}'.format(cpu_usage_graph.min_value))
        window['_MAX_CPU_'].update('Max: {}'.format(cpu_usage_graph.max_value))
        window['_MIN_MEM_'].update('Min: {}'.format(mem_usage_graph.min_value))
        window['_MAX_MEM_'].update('Max: {}'.format(mem_usage_graph.max_value))

if __name__ == '__main__':
    main()
