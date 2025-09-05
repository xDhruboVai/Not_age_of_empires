import math, time, random, sys

from OpenGL.GL import (
    glBegin, glEnd, glClear, glColor3f, glColor4f, glLoadIdentity, glMatrixMode, glPointSize,
    glPopMatrix, glPushMatrix, glRasterPos2f, glRotatef, glScalef, glTranslatef,
    glVertex3f, glViewport, glVertex2f, glBlendFunc, glClearColor,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, GL_LINES, GL_QUADS, GL_MODELVIEW,
    GL_PROJECTION, GL_DEPTH_TEST, glEnable, GL_BLEND, GL_SRC_ALPHA,
    GL_ONE_MINUS_SRC_ALPHA, glDisable
)
from OpenGL.GLU import (
    gluCylinder, gluLookAt, gluNewQuadric, gluOrtho2D, gluPerspective, gluSphere
)
from OpenGL.GLUT import (
    glutBitmapCharacter, glutCreateWindow, glutDisplayFunc, glutIdleFunc, glutInit,
    glutInitDisplayMode, glutInitWindowPosition, glutInitWindowSize, glutKeyboardFunc,
    glutMainLoop, glutMouseFunc, glutPostRedisplay, glutSolidCube, glutSpecialFunc,
    glutSwapBuffers, GLUT_DOUBLE, GLUT_RGB, GLUT_DEPTH,
    GLUT_LEFT_BUTTON, GLUT_RIGHT_BUTTON, GLUT_DOWN,
    GLUT_BITMAP_HELVETICA_18,
    GLUT_KEY_LEFT, GLUT_KEY_RIGHT, GLUT_KEY_UP, GLUT_KEY_DOWN
)

# CONSTRAINTS AND CONFIGS
WIDTH = 1000
HEIGHT = 700
ground_y = 0.0

# boss
boss_base_hp = 400
boss_hp_wave_scale = 80
boss_speed = 1
boss_radius = 0.9
boss_reward = 120

# enemies / towers / bullets
enemy_radius = 0.35
bullet_radius = 0.12
tower_default_radius = 6.0
tower_firerate = 0.9
tower_dmg = 20
bullet_speed = 8.0

# player
player_hp = 100
player_start_money = float("inf")
tower_cost = 75
kill_reward = 15
leak_dmg = 10

# abilities
abilitycost_fast = 100
abilitycost_explosive = 150
abilitycost_meteor = 200
abilitycost_mega_knight = 500
ability_fast_duration = 10.0
ability_explosive_duration = 10.0
ability_fast_multiplier = 2.0
mega_knight_duration = 20.0

# meteor
meteor_fall_speed = 14.0
meteor_radius = 2.5
meteor_aoe_radius = 9999.0

# rendering
sphere_slices = 18
sphere_stacks = 14

# sky
sky_wall_extent = 120.0
sky_wall_height = 60.0
sky_color = (0.70, 0.88, 1.00)

# map
class MapPreset:
    def __init__(self, name, path_points, tower_slots, path_width, ground_scale, camera_distance):
        self.name = name
        self.path_points = path_points
        self.tower_slots = tower_slots
        self.path_width = path_width
        self.ground_scale = ground_scale
        self.camera_distance = camera_distance

DEFAULT_MAP = MapPreset(
    name = "Default",
    path_points = [(-4.0, -4.0), (-4.0, -2.0), (0.0, -2.0), (2.0, -2.0), (2.0, 2.0), (4.0, 2.0)],
    tower_slots = [(-5.5, -2.0), (-2.0, -1.5), (0.5, -1.0), (2.0, -1.0), (1.5, 2.0), (3.5, 2.0)],
    path_width = 1.2,
    ground_scale = (20.0, 1.0, 15.0),
    camera_distance = 16.0
)

Mohammadpur = MapPreset(
    name = "Mohammadpur",
    path_points = [(-28.0, -18.0), (-28.0, -10.0), (-16.0, -10.0), (-16.0, -16.0), (-4.0, -16.0),
                   (-4.0, -6.0), (8.0, -6.0), (8.0, 6.0), (-12.0, 6.0), (-12.0, 14.0), (-2.0, 14.0),
                   (-2.0, 2.0), (14.0, 2.0), (14.0, -8.0), (24.0, -8.0), (24.0, 12.0), (6.0, 12.0),
                   (6.0, 18.0), (28.0, 18.0)],
    tower_slots = [(-29.5, -14.0), (-20.0, -10.0), (-6.0, -16.0), (8.0, -1.0), (0.0, 6.0), (-12.0, 10.0),
                   (4.0, 14.0), (14.0, -3.0), (24.0, 5.0), (7.5, 18.0)],
    path_width = 1.6,
    ground_scale = (60.0, 1.0, 40.0),
    camera_distance = 34.0
)

MAPS = {"Default": DEFAULT_MAP, "Mohammadpur": Mohammadpur}

# math helpers
def dist2D(ax, az, bx, bz):
    return math.hypot(bx - ax, bz - az)

def normalize2D(dx, dz):
    mag = math.hypot(dx, dz)
    if mag <= 1e-6:
        return (0.0, 0.0)
    return (dx / mag, dz / mag)

def clamp(value, lo, hi):
    return max(lo, min(hi, value))

# enemy
class Enemy:
    def __init__(self, x, z, speed, health, is_boss = False):
        self.x = x
        self.z = z
        self.y = ground_y + enemy_radius
        self.speed = speed
        self.health = health
        self.is_boss = is_boss
        self.radius = (boss_radius if is_boss else enemy_radius)
        self.path_idx = 0
        self.alive = True

    def is_dead(self):
        return self.health <= 0 or not self.alive

# projectile
class Projectile:
    def __init__(self, x, y, z, dir_x, dir_y, dir_z, speed, damage, explosive = False):
        self.x = x
        self.y = y
        self.z = z
        self.dx = dir_x
        self.dy = dir_y
        self.dz = dir_z
        self.speed = speed
        self.damage = damage
        self.radius = bullet_radius
        self.lifetime = 0.0
        self.max_lifetime = 5.0
        self.explosive = explosive
        self.explosion_radius = 2.2 if explosive else 0.0
        self.alive = True

# tower
class Tower:
    def __init__(self, x, z):
        self.x = x
        self.z = z
        self.y = ground_y
        self.range = tower_default_radius
        self.base_fire_interval = tower_firerate
        self.cooldown = 0.0
        self.damage = tower_dmg
        self.projectile_speed = bullet_speed
        self.rotate_degree = 0.0
        self.active = True

    def effective_interval(self, abilities):
        interval = self.base_fire_interval
        if abilities.fast_attack_active:
            interval = interval / ability_fast_multiplier
        return interval

# tower slot
class TowerSlot:
    def __init__(self, x, z):
        self.x = x
        self.z = z
        self.occupied = False
        self.tower = None

# player
class Player:
    def __init__(self):
        self.health = player_hp
        self.money = 0
        self.score = 0

# abilities
class Abilities:
    def __init__(self):
        self.fast_attack_active = False
        self.fast_attack_ends_at = 0.0
        self.explosive_active = False
        self.explosive_ends_at = 0.0
        self.meteors = []
        self.mega_knight = None

    def update(self, now, dt):
        if self.fast_attack_active and now >= self.fast_attack_ends_at:
            self.fast_attack_active = False
        if self.explosive_active and now >= self.explosive_ends_at:
            self.explosive_active = False

        if self.mega_knight and self.mega_knight.alive:
            self.mega_knight.update(dt)

    def activate_mega_knight(self, game):
        if game.player.money < abilitycost_mega_knight:
            return False
        game.player.money -= abilitycost_mega_knight
        self.mega_knight = MegaKnight()

        self.mega_knight.x = 0.0
        self.mega_knight.z = 0.0
        self.mega_knight.y = ground_y + 0.5
        self.mega_knight.active = True
        self.mega_knight.timer = mega_knight_duration
        return True

class MegaKnight:
    def __init__(self):
        self.x = 0.0
        self.z = 0.0
        self.y = ground_y + 0.5
        self.radius = 2.0
        self.health = 1000
        self.alive = True

        # movement + detection
        self.walk_speed = 7.0
        self.detect_radius = 15.0

        # charge + jump
        self.charge_time = 2
        self.charge_timer = 0.0
        self.is_charging = False

        self.jump_duration = 0.8
        self.jump_time = 0.0
        self.jump_height = 8.0
        self.start_x = 0.0
        self.start_z = 0.0
        self.lock_x = None
        self.lock_z = None

        # damage
        self.landing_damage = 220.0
        self.aoe_radius = 5.0

        self.active = False
        self.timer = 0.0

        # facing
        self.rotate_degree = 0.0
        self.allow_manual = False

    def update(self, dt):
        if not self.active or not self.alive:
            return

        self.timer -= dt
        if self.timer <= 0.0:
            self.alive = False
            return

        if self.jump_time > 0.0:
            if self.lock_x is not None:
                dx, dz = (self.lock_x - self.x), (self.lock_z - self.z)
                if abs(dx) + abs(dz) > 1e-5:
                    self.rotate_degree = math.degrees(math.atan2(dx, dz))

            t_left = self.jump_time - dt
            if t_left < 0.0:
                t_left = 0.0
            progress = 1.0 - (t_left / self.jump_duration if self.jump_duration > 1e-6 else 1.0)

            if self.lock_x is None:
                self.lock_x = self.x
                self.lock_z = self.z

            nx = self.start_x + (self.lock_x - self.start_x) * progress
            nz = self.start_z + (self.lock_z - self.start_z) * progress
            ny = ground_y + 0.5 + 4.0 * self.jump_height * progress * (1.0 - progress)

            self.x, self.z, self.y = nx, nz, ny
            self.jump_time = t_left

            if self.jump_time <= 0.0:
                # land
                self.x = self.lock_x
                self.z = self.lock_z
                self.y = ground_y + 0.5
                self.deal_landing_damage()
                # reset state
                self.is_charging = False
                self.charge_timer = 0.0
                self.lock_x = None
                self.lock_z = None
            return

        if self.is_charging:
            if self.lock_x is not None:
                dx, dz = (self.lock_x - self.x), (self.lock_z - self.z)
                if abs(dx) + abs(dz) > 1e-5:
                    self.rotate_degree = math.degrees(math.atan2(dx, dz))
            self.charge_timer -= dt
            if self.charge_timer <= 0.0 and self.lock_x is not None:
                self.start_x = self.x
                self.start_z = self.z
                self.jump_time = self.jump_duration
            return

        base_x, base_z = G.map.path_points[-1]
        front = None
        best_goal_dist = 1e9
        for e in G.enemies:
            if not e.alive:
                continue
            gd = dist2D(e.x, e.z, base_x, base_z)
            if gd < best_goal_dist:
                best_goal_dist = gd
                front = e

        if front:
            dx, dz = (front.x - self.x), (front.z - self.z)
            ndx, ndz = normalize2D(dx, dz)
            self.x += ndx * self.walk_speed * dt
            self.z += ndz * self.walk_speed * dt

            if abs(dx) + abs(dz) > 1e-5:
                self.rotate_degree = math.degrees(math.atan2(dx, dz))

            cand = None
            cand_goal = 1e9
            for e in G.enemies:
                if not e.alive:
                    continue
                if dist2D(self.x, self.z, e.x, e.z) <= self.detect_radius:
                    gd = dist2D(e.x, e.z, base_x, base_z)
                    if gd < cand_goal:
                        cand_goal = gd
                        cand = e
            if cand:
                self.lock_x = cand.x
                self.lock_z = cand.z
                self.is_charging = True
                self.charge_timer = self.charge_time

    def start_jump(self, dir_x, dir_z):
        mag = math.hypot(dir_x, dir_z)
        if mag <= 1e-6:
            return
        dir_x, dir_z = (dir_x / mag, dir_z / mag)
        self.start_x = self.x
        self.start_z = self.z
        self.lock_x = self.x + dir_x * 10.0
        self.lock_z = self.z + dir_z * 10.0
        self.is_charging = False
        self.charge_timer = 0.0
        self.jump_time = self.jump_duration

    def deal_landing_damage(self):
        for e in G.enemies:
            if not e.alive:
                continue
            if dist2D(self.x, self.z, e.x, e.z) <= self.aoe_radius:
                e.health -= self.landing_damage
                if e.health <= 0 and e.alive:
                    e.alive = False
                    G.player.money += (boss_reward if e.is_boss else kill_reward)
                    G.player.score += (50 if e.is_boss else 10)
        G.shake_timer = 1.0
        G.shake_mag = 0.6

    def draw(self, quadric):
        if not self.alive:
            return
        glPushMatrix()

        s = self.radius
        base_lift = 1.09 * s - 0.5
        glTranslatef(self.x, self.y + base_lift, self.z)
        glRotatef(self.rotate_degree, 0, 1, 0)

        s = self.radius

        # cape (back)
        glPushMatrix()
        glTranslatef(0.0, 0.8 * s, -0.5 * s)
        glColor3f(0.06, 0.12, 0.55)
        glScalef(1.0 * s, 1.3 * s, 0.08 * s)
        glutSolidCube(1.0)
        glPopMatrix()

        # torso (armor)
        glPushMatrix()
        glTranslatef(0.0, 0.55 * s, 0.0)
        glColor3f(0.42, 0.44, 0.50)
        glScalef(1.5 * s, 1.1 * s, 1.0 * s)
        glutSolidCube(1.0)
        glPopMatrix()

        # chest plate accent
        glPushMatrix()
        glTranslatef(0.0, 0.7 * s, 0.45 * s)
        glColor3f(0.18, 0.20, 0.24)
        glScalef(0.9 * s, 0.4 * s, 0.08 * s)
        glutSolidCube(1.0)
        glPopMatrix()

        # belt
        glPushMatrix()
        glTranslatef(0.0, 0.12 * s, 0.0)
        glColor3f(0.35, 0.25, 0.15)
        glScalef(1.3 * s, 0.25 * s, 0.95 * s)
        glutSolidCube(1.0)
        glPopMatrix()

        # belt buckle
        glPushMatrix()
        glTranslatef(0.0, 0.12 * s, 0.49 * s)
        glColor3f(0.85, 0.65, 0.20)
        glScalef(0.35 * s, 0.2 * s, 0.06 * s)
        glutSolidCube(1.0)
        glPopMatrix()

        # shoulder pads
        glPushMatrix()
        glTranslatef(-0.95 * s, 1.05 * s, 0.0)
        glColor3f(0.20, 0.20, 0.25)
        gluSphere(quadric, 0.42 * s, sphere_slices, sphere_stacks)
        glPopMatrix()

        glPushMatrix()
        glTranslatef(0.95 * s, 1.05 * s, 0.0)
        glColor3f(0.20, 0.20, 0.25)
        gluSphere(quadric, 0.42 * s, sphere_slices, sphere_stacks)
        glPopMatrix()

        # upper arms
        glPushMatrix()
        glTranslatef(-1.15 * s, 0.7 * s, 0.0)
        glColor3f(0.28, 0.28, 0.35)
        glScalef(0.35 * s, 0.75 * s, 0.35 * s)
        glutSolidCube(1.0)
        glPopMatrix()

        glPushMatrix()
        glTranslatef(1.15 * s, 0.7 * s, 0.0)
        glColor3f(0.28, 0.28, 0.35)
        glScalef(0.35 * s, 0.75 * s, 0.35 * s)
        glutSolidCube(1.0)
        glPopMatrix()

        # gauntlets (hands)
        glPushMatrix()
        glTranslatef(-1.2 * s, 0.25 * s, 0.0)
        glColor3f(0.10, 0.10, 0.12)
        gluSphere(quadric, 0.24 * s, sphere_slices, sphere_stacks)
        glPopMatrix()

        glPushMatrix()
        glTranslatef(1.2 * s, 0.25 * s, 0.0)
        glColor3f(0.10, 0.10, 0.12)
        gluSphere(quadric, 0.24 * s, sphere_slices, sphere_stacks)
        glPopMatrix()

        # legs (small)
        glPushMatrix()
        glTranslatef(-0.38 * s, -0.35 * s, 0.0)
        glColor3f(0.25, 0.25, 0.30)
        glScalef(0.35 * s, 0.85 * s, 0.38 * s)
        glutSolidCube(1.0)
        glPopMatrix()

        glPushMatrix()
        glTranslatef(0.38 * s, -0.35 * s, 0.0)
        glColor3f(0.25, 0.25, 0.30)
        glScalef(0.35 * s, 0.85 * s, 0.38 * s)
        glutSolidCube(1.0)
        glPopMatrix()

        # boots
        glPushMatrix()
        glTranslatef(-0.38 * s, -0.95 * s, 0.1 * s)
        glColor3f(0.10, 0.10, 0.12)
        glScalef(0.7 * s, 0.28 * s, 1.0 * s)
        glutSolidCube(1.0)
        glPopMatrix()

        glPushMatrix()
        glTranslatef(0.38 * s, -0.95 * s, 0.1 * s)
        glColor3f(0.10, 0.10, 0.12)
        glScalef(0.7 * s, 0.28 * s, 1.0 * s)
        glutSolidCube(1.0)
        glPopMatrix()

        # head (helmet dome)
        glPushMatrix()
        glTranslatef(0.0, 1.25 * s, 0.0)
        glColor3f(0.30, 0.31, 0.34)
        gluSphere(quadric, 0.38 * s, sphere_slices, sphere_stacks)
        glPopMatrix()

        # visor
        glPushMatrix()
        glTranslatef(0.0, 1.15 * s, 0.38 * s)
        glColor3f(0.05, 0.05, 0.08)
        glScalef(0.55 * s, 0.20 * s, 0.07 * s)
        glutSolidCube(1.0)
        glPopMatrix()

        # helmet crest
        glPushMatrix()
        glTranslatef(0.0, 1.55 * s, 0.0)
        glColor3f(0.15, 0.30, 0.85)
        glScalef(0.35 * s, 0.45 * s, 0.35 * s)
        glutSolidCube(1.0)
        glPopMatrix()

        glPopMatrix()

def apply_screen_shake():
    if G.shake_timer <= 0.0:
        return
    duration = 1.0
    decay = G.shake_timer / duration
    amp = G.shake_mag * decay

    t = time.perf_counter()
    ox = math.sin(t * G.shake_freq) * amp
    oy = math.cos(t * G.shake_freq * 1.3) * amp * 0.5
    oz = math.sin(t * G.shake_freq * 0.7 + 1.57) * amp

    glTranslatef(ox, oy, oz)

# Meteor
class Meteor:
    def __init__(self, x, z):
        self.x = x
        self.z = z
        self.y = 40.0
        self.radius = meteor_radius
        self.speed = meteor_fall_speed
        self.alive = True

    def update(self, dt):
        if not self.alive:
            return
        self.y -= self.speed * dt
        if self.y <= ground_y + 0.1:
            self.alive = False
            G.shake_timer = 1
            G.shake_mag = 1

# waves
class WaveManager:
    def __init__(self):
        self.wave_num = 1
        self.spawn_interval = 1.2
        self.time_to_next = 2.0
        self.to_spawn = 8
        self.between_waves = 4.0
        self.resting = False
        self.boss_spawned = False
        self.middle_boss_spawned = False

    def update(self, dt, game):
        if self.resting:
            self.time_to_next -= dt
            if self.time_to_next <= 0:
                self.resting = False
                self.boss_spawned = False
                self.middle_boss_spawned = False
                self.to_spawn = 8 + self.wave_num * 2
                self.spawn_interval = max(0.4, 1.2 - 0.05 * self.wave_num)
                self.time_to_next = self.spawn_interval
            return

        if self.to_spawn > 0:
            self.time_to_next -= dt
            if self.time_to_next <= 0:
                self.time_to_next = self.spawn_interval
                self.to_spawn -= 1
                spawn_enemy(game, speed = 1.2 + 0.05 * self.wave_num, health = 60 + 10 * self.wave_num)

                if not self.middle_boss_spawned and self.to_spawn <= self.wave_num:
                    self.middle_boss_spawned = True
                    spawn_boss(game)

            return

        if not self.boss_spawned:
            self.boss_spawned = True
            num_bosses = math.ceil(self.wave_num / 3)
            for _ in range(num_bosses):
                spawn_boss(game)
            return

        if not any(e.alive for e in game.enemies):
            self.resting = True
            self.wave_num += 1
            self.time_to_next = self.between_waves


# camera
class Camera:
    def __init__(self):
        self.target_x, self.target_y, self.target_z = (0.0, 0.0, 0.0)
        self.distance = 16.0
        self.rotate = 35.0
        self.pitch = 35.0

    def eye(self):
        rotate_r = math.radians(self.rotate)
        pitch_r = math.radians(self.pitch)
        cx = self.target_x + self.distance * math.cos(pitch_r) * math.sin(rotate_r)
        cy = self.target_y + self.distance * math.sin(pitch_r)
        cz = self.target_z + self.distance * math.cos(pitch_r) * math.cos(rotate_r)
        return (cx, cy, cz)

# game state
class GameState:
    def __init__(self):
        self.game_state = 'MAIN_MENU'
        self.map_names = list(MAPS.keys())
        self.selected_map_idx = 0

        self.map = None
        self.player = None
        self.abilities = None
        self.wave = None
        self.enemies = []
        self.projectiles = []
        self.tower_slots = []
        self.camera = Camera()
        self.quadric = None
        self.last_time = 0.0
        self.shake_timer = 0.0
        self.shake_mag = 0.0
        self.shake_freq = 35.0

    def reset(self, start_game=True):
        selected_map_name = self.get_selected_map_name()
        self.map = MAPS[selected_map_name]

        self.player = Player()
        self.player.money = player_start_money
        self.abilities = Abilities()
        self.wave = WaveManager()
        self.enemies = []
        self.projectiles = []
        self.tower_slots = [TowerSlot(x, z) for (x, z) in self.map.tower_slots]

        self.camera.distance = self.map.camera_distance
        self.camera.target_x, self.camera.target_y, self.camera.target_z = (0.0, 0.0, 0.0)

        self.last_time = time.perf_counter()
        self.shake_timer = 0.0
        self.shake_mag = 0.0

        if start_game:
            self.game_state = 'PLAYING'

    def select_next_map(self):
        self.selected_map_idx = (self.selected_map_idx + 1) % len(self.map_names)

    def get_selected_map_name(self):
        return self.map_names[self.selected_map_idx]

    def activate_mega_knight(self):
        if not self.abilities.activate_mega_knight(self):
            print("Not enough money for Mega Knight!")

# spawn
def spawn_enemy(game, speed, health):
    x0, z0 = game.map.path_points[0]
    game.enemies.append(Enemy(x0, z0, speed * 1.5, health, is_boss = False))

def spawn_boss(game):
    x0, z0 = game.map.path_points[0]
    hp = boss_base_hp + (game.wave.wave_num - 1) * boss_hp_wave_scale
    game.enemies.append(Enemy(x0, z0, boss_speed, hp, is_boss = True))

# actions
def build_tower_at_slot(game, slot_idx):
    if slot_idx < 0 or slot_idx >= len(game.tower_slots):
        return False
    slot = game.tower_slots[slot_idx]
    if slot.occupied or game.player.money < tower_cost:
        return False
    slot.occupied = True
    slot.tower = Tower(slot.x, slot.z)
    game.player.money -= tower_cost
    return True

def activate_fast_attack(game, now):
    if game.player.money < abilitycost_fast:
        return False
    game.player.money -= abilitycost_fast
    game.abilities.fast_attack_active = True
    game.abilities.fast_attack_ends_at = now + ability_fast_duration
    return True

def activate_explosive(game, now):
    if game.player.money < abilitycost_explosive:
        return False
    game.player.money -= abilitycost_explosive
    game.abilities.explosive_active = True
    game.abilities.explosive_ends_at = now + ability_explosive_duration
    return True

def activate_meteor(game):
    if game.player.money < abilitycost_meteor:
        return False
    game.player.money -= abilitycost_meteor

    if game.enemies:
        tx = min(game.enemies, key=lambda e: dist2D(e.x, e.z, game.map.path_points[-1][0], game.map.path_points[-1][1])).x
        tz = min(game.enemies, key=lambda e: dist2D(e.x, e.z, game.map.path_points[-1][0], game.map.path_points[-1][1])).z
    else:
        mid = len(game.map.path_points) // 2
        tx, tz = game.map.path_points[mid]
    game.abilities.meteors.append(Meteor(tx, tz))
    return True


# updates
def update_game(game, dt):
    now = time.perf_counter()
    game.abilities.update(now, dt)
    game.wave.update(dt, game)
    update_enemies(game, dt)
    update_towers(game, dt)
    update_projectiles(game, dt)
    update_meteors(game, dt)

    if game.shake_timer > 0.0:
        game.shake_timer = max(0.0, game.shake_timer - dt)


def update_enemies(game, dt):
    path = game.map.path_points
    base_x, base_z = path[-1]
    survivors = []
    for e in game.enemies:
        if not e.alive:
            continue
        if e.path_idx < len(path) - 1:
            tx, tz = path[e.path_idx + 1]
            ndx, ndz = normalize2D(tx - e.x, tz - e.z)
            e.x += ndx * e.speed * dt
            e.z += ndz * e.speed * dt
            if dist2D(e.x, e.z, tx, tz) < 0.1:
                e.path_idx += 1
        if e.path_idx >= len(path) - 1 and dist2D(e.x, e.z, base_x, base_z) < 0.3:
            game.player.health -= leak_dmg
            e.alive = False
            if game.player.health <= 0:
                game.player.health = 0
                game.game_state = 'GAME_OVER'
        if not e.is_dead():
            survivors.append(e)
    game.enemies = survivors

def acquire_target(tower, enemies):
    best = None
    best_d = 1e9
    for e in enemies:
        if not e.alive:
            continue
        d = dist2D(tower.x, tower.z, e.x, e.z)
        if d <= tower.range and d < best_d:
            best = e
            best_d = d
    return best

def update_towers(game, dt):
    for slot in game.tower_slots:
        if not slot.occupied or not slot.tower.active:
            continue
        t = slot.tower
        t.cooldown -= dt  
        target = acquire_target(t, game.enemies)

        if target:
            dx, dz = (target.x - t.x), (target.z - t.z)

            t.rotate_degree = math.degrees(math.atan2(dz, dx))

            if t.cooldown <= 0.0:
                t.cooldown = t.effective_interval(game.abilities)

                dir_x, dir_z = normalize2D(dx, dz)
                dir_y = 0.1

                proj = Projectile(
                    x = t.x, y = t.y + 1.0, z = t.z, 
                    dir_x = dir_x, dir_y = dir_y, dir_z = dir_z,  
                    speed = t.projectile_speed,
                    damage = t.damage,
                    explosive = game.abilities.explosive_active
                )
                game.projectiles.append(proj)


def update_projectiles(game, dt):
    alive_proj = []
    for p in game.projectiles:
        if not p.alive:
            continue
        p.x += p.dx * p.speed * dt
        p.y += p.dy * p.speed * dt
        p.z += p.dz * p.speed * dt
        p.lifetime += dt
        if p.lifetime > p.max_lifetime or abs(p.x) > 80 or abs(p.z) > 80 or p.y < ground_y - 1:
            p.alive = False
            continue
        hit_enemy = None
        for e in game.enemies:
            if not e.alive:
                continue
            if dist2D(p.x, p.z, e.x, e.z) <= (p.radius + e.radius):
                hit_enemy = e
                break
        if hit_enemy:
            if p.explosive:
                for e in game.enemies:
                    if not e.alive:
                        continue
                    if dist2D(p.x, p.z, e.x, e.z) <= p.explosion_radius:
                        e.health -= p.damage
                        if e.health <= 0 and e.alive:
                            e.alive = False
                            game.player.money += (boss_reward if e.is_boss else kill_reward)
                            game.player.score += (50 if e.is_boss else 10)
            else:
                hit_enemy.health -= p.damage
                if hit_enemy.health <= 0 and hit_enemy.alive:
                    hit_enemy.alive = False
                    game.player.money += (boss_reward if hit_enemy.is_boss else kill_reward)
                    game.player.score += (50 if hit_enemy.is_boss else 10)
            p.alive = False
        if p.alive:
            alive_proj.append(p)
    game.projectiles = alive_proj

def update_meteors(game, dt):
    remaining = []
    for m in game.abilities.meteors:
        if m.alive:
            m.update(dt)
            if m.alive:
                remaining.append(m)
                continue
            # impact: wipe the board, boss loses 50% of remaining HP
            for e in game.enemies:
                if not e.alive:
                    continue
                if e.is_boss:
                    e.health *= 0.5
                    if e.health <= 0:
                        e.alive = False
                        game.player.money += boss_reward
                        game.player.score += 50
                else:
                    e.alive = False
                    game.player.money += kill_reward
                    game.player.score += 10
    game.abilities.meteors = remaining

# ui text
def draw_text_2d(x, y, s):
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WIDTH, 0, HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in s:
        glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(ch))
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()

# sky
def draw_sky_walls():
    sx, _, sz = G.map.ground_scale
    x = sx * 0.5 + 50.0
    z = sz * 0.5 + 50.0

    y_bottom = -100.0
    y_top = sky_wall_height

    r, g, b = sky_color
    glColor3f(r, g, b)

    # +Z wall
    glBegin(GL_QUADS)
    glVertex3f(-x, y_bottom,  z)
    glVertex3f( x, y_bottom,  z)
    glVertex3f( x, y_top,     z)
    glVertex3f(-x, y_top,     z)
    glEnd()

    # floor (bottom)
    glBegin(GL_QUADS)
    glVertex3f(-x, y_bottom,  z)
    glVertex3f( x, y_bottom,  z)
    glVertex3f( x, y_bottom, -z)
    glVertex3f(-x, y_bottom, -z)
    glEnd()

    # -Z wall
    glBegin(GL_QUADS)
    glVertex3f( x, y_bottom, -z)
    glVertex3f(-x, y_bottom, -z)
    glVertex3f(-x, y_top,   -z)
    glVertex3f( x, y_top,   -z)
    glEnd()

    # +X wall
    glBegin(GL_QUADS)
    glVertex3f( x, y_bottom, -z)
    glVertex3f( x, y_bottom,  z)
    glVertex3f( x, y_top,     z)
    glVertex3f( x, y_top,    -z)
    glEnd()

    # -X wall
    glBegin(GL_QUADS)
    glVertex3f(-x, y_bottom,  z)
    glVertex3f(-x, y_bottom, -z)
    glVertex3f(-x, y_top,   -z)
    glVertex3f(-x, y_top,    z)
    glEnd()

# ground
def draw_ground():
    sx, sy, sz = G.map.ground_scale
    glPushMatrix()
    glColor3f(0.35, 0.65, 0.35)
    glTranslatef(0.0, ground_y - 0.5, 0.0)
    glScalef(sx, sy, sz)
    glutSolidCube(1.0)
    glPopMatrix()

# path
def draw_path():
    glColor3f(0.85, 0.80, 0.70)
    pts = G.map.path_points
    width = G.map.path_width
    for i in range(len(pts) - 1):
        x0, z0 = pts[i]
        x1, z1 = pts[i + 1]
        dx, dz = (x1 - x0), (z1 - z0)
        nx, nz = normalize2D(-dz, dx)
        wx, wz = nx * width * 0.5, nz * width * 0.5
        y = ground_y + 0.01
        glBegin(GL_QUADS)
        glVertex3f(x0 - wx, y, z0 - wz)
        glVertex3f(x0 + wx, y, z0 + wz)
        glVertex3f(x1 + wx, y, z1 + wz)
        glVertex3f(x1 - wx, y, z1 - wz)
        glEnd()

# base
def draw_base():
    base_x, base_z = G.map.path_points[-1]
    glPushMatrix()
    glTranslatef(base_x, ground_y + 0.25, base_z)
    glColor3f(0.30, 0.95, 0.30)
    glScalef(1.8, 0.5, 1.8)
    glutSolidCube(1.0)
    glPopMatrix()

# tower slot
def draw_tower_slot(slot):
    glPushMatrix()
    glTranslatef(slot.x, ground_y + 0.05, slot.z)
    glColor3f(0.25, 0.25, 0.25)
    glScalef(0.9, 0.1, 0.9)
    glutSolidCube(1.0)
    glPopMatrix()

# tower draw
def draw_tower(t, quadric):
    glPushMatrix()
    glTranslatef(t.x, t.y, t.z)
    glRotatef(t.rotate_degree, 0, 1, 0)
    glColor3f(0.80, 0.80, 0.90)
    glPushMatrix()
    glTranslatef(0.0, 0.5, 0.0)
    glRotatef(-90, 1, 0, 0)
    gluCylinder(quadric, 0.25, 0.25, 1.0, 12, 1)
    glPopMatrix()
    glColor3f(0.95, 0.40, 0.30)
    glPushMatrix()
    glTranslatef(0.0, 1.1, 0.0)
    glRotatef(-90, 1, 0, 0)
    gluCylinder(quadric, 0.1, 0.1, 0.6, 10, 1)
    glPopMatrix()
    glPopMatrix()

# enemy draw
def draw_enemy(e, quadric):
    glPushMatrix()
    glTranslatef(e.x, e.y, e.z)
    if e.is_boss:
        glColor3f(0.6, 0.1, 0.9)
    else:
        glColor3f(0.2, 0.7, 0.9)
    gluSphere(quadric, e.radius, sphere_slices, sphere_stacks)
    glPopMatrix()

# projectile draw
def draw_projectile(p, quadric):
    glPushMatrix()
    glTranslatef(p.x, p.y, p.z)
    glColor3f(1.0, 0.6, 0.0 if p.explosive else 1.0)
    gluSphere(quadric, p.radius, 10, 10)
    glPopMatrix()

# meteor draw
def draw_meteor(m, quadric):
    glPushMatrix()
    glTranslatef(m.x, m.y, m.z)
    glColor3f(0.9, 0.3, 0.3)  
    gluSphere(quadric, m.radius, 14, 10)
    glPopMatrix()

# NEW: Menu and UI Drawing Functions
def draw_overlay():
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WIDTH, 0, HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    glColor4f(0.0, 0.0, 0.0, 0.6)
    glBegin(GL_QUADS)
    glVertex2f(0, 0)
    glVertex2f(WIDTH, 0)
    glVertex2f(WIDTH, HEIGHT)
    glVertex2f(0, HEIGHT)
    glEnd()

    glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST)

    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()

def draw_main_menu():
    glClearColor(0.1, 0.1, 0.2, 1.0)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glColor3f(1.0, 1.0, 1.0)
    draw_text_2d(WIDTH/2 - 100, HEIGHT - 100, "3D TOWER DEFENSE")
    draw_text_2d(WIDTH/2 - 150, HEIGHT - 200, f"Selected Map: {G.get_selected_map_name()}")
    draw_text_2d(WIDTH/2 - 150, HEIGHT - 250, "[S] Start Game")
    draw_text_2d(WIDTH/2 - 150, HEIGHT - 300, "[M] Change Map")
    draw_text_2d(WIDTH/2 - 150, HEIGHT - 350, "[Q] Quit")

def draw_pause_menu():
    draw_overlay()
    glColor3f(1.0, 1.0, 1.0)
    draw_text_2d(WIDTH/2 - 50, HEIGHT - 200, "PAUSED")
    draw_text_2d(WIDTH/2 - 100, HEIGHT - 250, "[P] Resume Game")
    draw_text_2d(WIDTH/2 - 100, HEIGHT - 300, "[R] Restart")
    draw_text_2d(WIDTH/2 - 100, HEIGHT - 350, "[T] Return to Main Menu")
    draw_text_2d(WIDTH/2 - 100, HEIGHT - 400, "[Q] Quit")

def draw_game_over_screen():
    draw_overlay()
    glColor3f(1.0, 0.2, 0.2)
    draw_text_2d(WIDTH/2 - 70, HEIGHT - 200, "GAME OVER")
    glColor3f(1.0, 1.0, 1.0)
    draw_text_2d(WIDTH/2 - 100, HEIGHT - 250, f"Final Score: {G.player.score}")
    draw_text_2d(WIDTH/2 - 100, HEIGHT - 300, "[R] Restart")
    draw_text_2d(WIDTH/2 - 100, HEIGHT - 350, "[T] Return to Main Menu")

# global state
G = GameState()

# Main drawing functions
def draw_game_world():
    glViewport(0, 0, WIDTH, HEIGHT)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(60.0, WIDTH / float(HEIGHT), 0.1, 300.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    ex, ey, ez = G.camera.eye()
    gluLookAt(ex, ey, ez, G.camera.target_x, G.camera.target_y, G.camera.target_z, 0, 1, 0)

    apply_screen_shake()

    # world
    draw_sky_walls()
    draw_ground()
    draw_path()
    draw_base()

    for slot in G.tower_slots:
        draw_tower_slot(slot)
        if slot.occupied:
            draw_tower(slot.tower, G.quadric)

    for e in G.enemies:
        draw_enemy(e, G.quadric)
    for p in G.projectiles:
        draw_projectile(p, G.quadric)
    for m in G.abilities.meteors:
        draw_meteor(m, G.quadric)

    if G.abilities.mega_knight and G.abilities.mega_knight.alive:
        G.abilities.mega_knight.draw(G.quadric)

    # hud
    glColor3f(0.0, 0.0, 0.0)
    draw_text_2d(10, HEIGHT - 24, f"Health: {G.player.health}   Money: {G.player.money}   Score: {G.player.score}   Wave: {G.wave.wave_num}   Map: {G.map.name}")
    draw_text_2d(10, HEIGHT - 48, "[P] Pause | [1-0] Build | F: Fast | E: Explosive | M: Meteor | G: Mega Knight | Arrows: Camera")

    mk = G.abilities.mega_knight
    if mk and mk.alive:
        info = f"MK Active: {mk.timer:.1f}s remaining"
        draw_text_2d(10, HEIGHT - 72, info)
    else:
        draw_text_2d(10, HEIGHT - 72, f"Mega Knight Cost: {abilitycost_mega_knight} | [G] to Summon")

def display():
    if G.game_state == 'MAIN_MENU':
        draw_main_menu()
    else:
        glClearColor(sky_color[0], sky_color[1], sky_color[2], 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        draw_game_world()
        if G.game_state == 'PAUSED':
            draw_pause_menu()
        elif G.game_state == 'GAME_OVER':
            draw_game_over_screen()

    glutSwapBuffers()


# idle
def idle():
    now = time.perf_counter()
    if G.last_time == 0.0:
        G.last_time = now
    dt = now - G.last_time
    G.last_time = now

    if G.game_state == 'PLAYING':
        update_game(G, dt)

    glutPostRedisplay()

# input
def keyboard(key, x, y):
    k = key.decode('utf-8').lower()
    now = time.perf_counter()

    if G.game_state == 'MAIN_MENU':
        if k == 's':
            G.reset() 
        elif k == 'm':
            G.select_next_map()
        elif k == 'q':
            sys.exit(0)

    elif G.game_state == 'PLAYING':
        if k == 'p':
            G.game_state = 'PAUSED'
        elif k in '1234567890':
            idx = 9 if k == '0' else (ord(k) - ord('1'))
            build_tower_at_slot(G, idx)
        elif k == 'f':
            activate_fast_attack(G, now)
        elif k == 'e':
            activate_explosive(G, now)
        elif k == 'm':
            activate_meteor(G)
        elif k == 'g':
            G.activate_mega_knight()
        elif k == 'q':
            sys.exit(0)

    elif G.game_state == 'PAUSED':
        if k == 'p':
            G.game_state = 'PLAYING'
            G.last_time = time.perf_counter()
        elif k == 'r':
            G.reset()
        elif k == 't':
            G.game_state = 'MAIN_MENU'
        elif k == 'q':
            sys.exit(0)

    elif G.game_state == 'GAME_OVER':
        if k == 'r':
            G.reset()
        elif k == 't':
            G.game_state = 'MAIN_MENU'

def special(key, x, y):
    if G.game_state != 'PLAYING':
        return
    if key == GLUT_KEY_LEFT:
        G.camera.rotate -= 3
    if key == GLUT_KEY_RIGHT:
        G.camera.rotate += 3
    if key == GLUT_KEY_UP:
        G.camera.pitch = clamp(G.camera.pitch + 2, 10, 80)
    if key == GLUT_KEY_DOWN:
        G.camera.pitch = clamp(G.camera.pitch - 2, 10, 80)

def mouse(button, state, x, y):
    if G.game_state != 'PLAYING':
        return 
    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        if G.abilities.mega_knight and G.abilities.mega_knight.alive and G.abilities.mega_knight.allow_manual:
            win_x, win_y = x, y
            direction_x = (win_x - WIDTH / 2) / WIDTH
            direction_z = (win_y - HEIGHT / 2) / HEIGHT
            G.abilities.mega_knight.start_jump(direction_x, direction_z)

# init
def init_glut():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WIDTH, HEIGHT)
    glutInitWindowPosition(100, 100)
    glutCreateWindow(b"CSE423 3D Tower Defense")

    glEnable(GL_DEPTH_TEST)
    G.quadric = gluNewQuadric()

    glutDisplayFunc(display)
    glutIdleFunc(idle)
    glutKeyboardFunc(keyboard)
    glutSpecialFunc(special)
    glutMouseFunc(mouse)

# main
def main():
    init_glut()
    glutMainLoop()

if __name__ == "__main__":
    main()