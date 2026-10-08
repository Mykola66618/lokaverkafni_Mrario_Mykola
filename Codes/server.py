"""Distance Duel - Raspberry Pi NiceGUI + Mosquitto MQTT server.

Run from the installed virtualenv and systemd distance-game.service.
Both ESP32 players can shoot once per round, in either order.
"""

import asyncio
import math
import queue
import random

import paho.mqtt.client as mqtt
from nicegui import app, ui

MQTT_HOST = '127.0.0.1'  # Broker is on this Raspberry Pi
MQTT_PORT = 1883
P1_TOPIC = 'game/player1/shot'
P2_TOPIC = 'game/player2/shot'
TARGET_TOPIC = 'game/target'
PLAYER_TOPIC = 'game/player'
RESULT_TOPIC = 'game/result'
NEW_ROUND_TOPIC = 'game/new_round'


class DistanceDuel:
    def __init__(self):
        self.target = None
        self.p1 = None
        self.p2 = None
        self.score1 = 0
        self.score2 = 0
        self.round_number = 0
        self.finished = False
        self.winner = ''
        self.status = 'CONNECTING TO MQTT...'
        self.connected = False
        self.events = queue.Queue()
        self.task = None

        self.mqtt = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id='distance_duel_pi_single_v4',
            protocol=mqtt.MQTTv311,
        )
        self.mqtt.on_connect = self.on_connect
        self.mqtt.on_disconnect = self.on_disconnect
        self.mqtt.on_message = self.on_message

    # MQTT callbacks run on the MQTT thread. Only enqueue events here;
    # NiceGUI/game state updates happen on the asyncio event loop.
    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            self.connected = False
            print('MQTT CONNECT FAILED:', reason_code, flush=True)
            return
        self.connected = True
        print('MQTT CONNECTED', flush=True)
        client.subscribe([
            (P1_TOPIC, 0),
            (P2_TOPIC, 0),
            (NEW_ROUND_TOPIC, 0),
        ])
        self.events.put(('connected', ''))

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        print('MQTT DISCONNECTED:', reason_code, flush=True)

    def on_message(self, client, userdata, msg):
        payload = msg.payload.decode('utf-8', errors='replace').strip()
        print('MQTT RECEIVED:', msg.topic, payload, flush=True)
        self.events.put((msg.topic, payload))

    def publish(self, topic, message, retain=False):
        if not self.mqtt.is_connected():
            print('MQTT OFFLINE: cannot publish', topic, flush=True)
            return False
        info = self.mqtt.publish(topic, str(message), qos=1, retain=retain)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            print('MQTT PUBLISH FAILED:', topic, info.rc, flush=True)
            return False
        return True

    def new_round(self):
        if not self.mqtt.is_connected():
            self.status = 'MQTT DISCONNECTED - CANNOT START ROUND'
            print('NEW ROUND BLOCKED: MQTT offline', flush=True)
            return

        self.round_number += 1
        self.target = random.randint(20, 100)
        self.p1 = None
        self.p2 = None
        self.finished = False
        self.winner = ''
        self.status = 'BOTH PLAYERS CAN SHOOT!'

        # One target for the whole round, retained for controllers that
        # connect late. Do not re-publish it on every MQTT reconnect.
        self.publish(TARGET_TOPIC, self.target, retain=True)
        self.publish(PLAYER_TOPIC, '0', retain=True)
        # game/result is NOT retained; no need to publish an empty result.
        print(f'NEW ROUND #{self.round_number}: TARGET {self.target} cm', flush=True)

    def handle_shot(self, player, payload):
        if self.target is None or self.finished:
            print('SHOT IGNORED: no active round', flush=True)
            return
        if (player == 1 and self.p1 is not None) or (player == 2 and self.p2 is not None):
            print(f'SHOT IGNORED: player {player} has already shot', flush=True)
            return
        try:
            distance = float(payload)
        except ValueError:
            print('SHOT IGNORED: invalid number:', payload, flush=True)
            return
        if not math.isfinite(distance) or not 2 <= distance <= 400:
            print('SHOT IGNORED: out of range:', distance, flush=True)
            return

        distance = round(distance, 1)
        if player == 1:
            self.p1 = distance
        else:
            self.p2 = distance
        print(f'PLAYER {player} SHOT: {distance} cm', flush=True)

        if self.p1 is None or self.p2 is None:
            self.status = 'WAITING FOR SECOND SHOT...'
            return

        error1 = abs(self.p1 - self.target)
        error2 = abs(self.p2 - self.target)
        self.finished = True
        self.status = 'ROUND FINISHED'
        if abs(error1 - error2) < 0.0001:
            self.winner = 'DRAW'
        elif error1 < error2:
            self.winner = 'PLAYER 1'
            self.score1 += 1
        else:
            self.winner = 'PLAYER 2'
            self.score2 += 1

        self.publish(RESULT_TOPIC, self.winner)
        print('RESULT:', self.winner,
              '| TARGET:', self.target,
              '| P1:', self.p1,
              '| P2:', self.p2, flush=True)

    async def process_events(self):
        while True:
            for _ in range(100):
                try:
                    topic, payload = self.events.get_nowait()
                except queue.Empty:
                    break
                if topic == 'connected':
                    if self.round_number == 0:
                        self.new_round()
                elif topic == NEW_ROUND_TOPIC:
                    self.new_round()
                elif topic == P1_TOPIC:
                    self.handle_shot(1, payload)
                elif topic == P2_TOPIC:
                    self.handle_shot(2, payload)
            await asyncio.sleep(0.05)

    def start(self):
        print('STARTING MQTT...', flush=True)
        self.mqtt.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
        self.mqtt.loop_start()
        self.task = asyncio.create_task(self.process_events())

    def stop(self):
        if self.task is not None:
            self.task.cancel()
        self.mqtt.disconnect()
        self.mqtt.loop_stop()


# SINGLE shared game object. Using @ui.page (not NiceGUI script mode)
# prevents a second runpy execution with separate game state.
game = DistanceDuel()


@app.on_startup
async def start_server():
    game.start()


@app.on_shutdown
def stop_server():
    game.stop()


@ui.page('/')
def home():
    ui.add_head_html('''
    <style>
      body { background: #0b1220; color: white; }
      .duel-card { background: #172235; border-radius: 18px;
                   min-width: 220px; padding: 24px; text-align: center; }
    </style>
    ''')

    with ui.column().classes('w-full items-center gap-5 p-6'):
        ui.label('DISTANCE DUEL').classes('text-4xl font-bold text-white')
        ui.label('Both players can shoot at any time').classes('text-gray-400')
        mqtt_label = ui.label('MQTT: CONNECTING...').classes('text-sm text-yellow-400')
        ui.separator()
        ui.label('TARGET DISTANCE').classes('text-lg text-gray-300')
        target_label = ui.label('-- cm').classes('text-6xl font-bold text-blue-400')
        round_label = ui.label('ROUND 0').classes('text-gray-400')
        ui.separator()

        with ui.row().classes('w-full justify-center gap-6 flex-wrap'):
            with ui.column().classes('duel-card items-center gap-2'):
                ui.label('PLAYER 1').classes('text-2xl font-bold text-red-400')
                p1_label = ui.label('-- cm').classes('text-4xl font-bold')
                p1_error = ui.label('Error: --')
                p1_status = ui.label('WAITING').classes('text-yellow-400')
                p1_score = ui.label('WINS: 0').classes('text-xl font-bold')
            with ui.column().classes('duel-card items-center gap-2'):
                ui.label('PLAYER 2').classes('text-2xl font-bold text-blue-400')
                p2_label = ui.label('-- cm').classes('text-4xl font-bold')
                p2_error = ui.label('Error: --')
                p2_status = ui.label('WAITING').classes('text-yellow-400')
                p2_score = ui.label('WINS: 0').classes('text-xl font-bold')

        ui.separator()
        status_label = ui.label('STARTING...').classes('text-2xl font-bold text-white')
        winner_label = ui.label('').classes('text-3xl font-bold text-green-400')
        ui.button('NEW ROUND', on_click=game.new_round, color='primary').classes('text-xl px-10 py-4')

    def refresh():
        mqtt_label.set_text('MQTT: CONNECTED' if game.connected else 'MQTT: DISCONNECTED')
        target_label.set_text('-- cm' if game.target is None else f'{game.target} cm')
        round_label.set_text(f'ROUND {game.round_number}')
        p1_label.set_text('-- cm' if game.p1 is None else f'{game.p1:.1f} cm')
        p2_label.set_text('-- cm' if game.p2 is None else f'{game.p2:.1f} cm')
        p1_error.set_text('Error: --' if game.p1 is None else f'Error: {abs(game.p1 - game.target):.1f} cm')
        p2_error.set_text('Error: --' if game.p2 is None else f'Error: {abs(game.p2 - game.target):.1f} cm')
        p1_status.set_text('SHOT RECEIVED' if game.p1 is not None else 'READY')
        p2_status.set_text('SHOT RECEIVED' if game.p2 is not None else 'READY')
        p1_score.set_text(f'WINS: {game.score1}')
        p2_score.set_text(f'WINS: {game.score2}')
        status_label.set_text(game.status)
        winner_label.set_text('' if not game.winner else
                              'DRAW!' if game.winner == 'DRAW' else f'{game.winner} WINS!')

    refresh()
    ui.timer(0.2, refresh)


if __name__ == '__main__':
    ui.run(
        host='0.0.0.0',
        port=8080,
        title='Distance Duel',
        reload=False,
        show=False,
    )
