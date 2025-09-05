import math, time, random

from OpenGL.GL import (
    glBegin, glEnd, glClear, glColor3f, glLoadIdentity, glMatrixMode, glPointSize,
    glPopMatrix, glPushMatrix, glRasterPos2f, glRotatef, glScalef, glTranslatef,
    glVertex3f, glViewport,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, GL_LINES, GL_QUADS, GL_MODELVIEW,
    GL_PROJECTION, GL_DEPTH_TEST, glEnable
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
tower_cost = 75
kill_reward = 15
leak_dmg = 10

# abilities
abilitycost_fast = 100
abilitycost_explosive = 150
abilitycost_meteor = 200
ability_fast_duration = 10.0
ability_explosive_duration = 10.0
ability_fast_multiplier = 2.0

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
    path_points = [(-8.0, -6.0), (-8.0, -2.0), (-4.0, -2.0), (0.0, -2.0), (0.0, 2.0), (5.0, 2.0), (8.0, 2.0)],
    tower_slots = [(-9.5, -4.0), (-6.0, -3.5), (-2.5, -3.0), (1.5, -3.0), (1.5, 3.0), (4.0, 3.0), (7.0, 3.0)],
    path_width = 1.2,
    ground_scale = (30.0, 1.0, 20.0),
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
SELECTED_MAP = "Mohammadpur"

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
        self.yaw_deg = 0.0
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
        self.money = float("inf")
        self.score = 0

# abilities
class Abilities:
    def __init__(self):
        self.fast_attack_active = False
        self.fast_attack_ends_at = 0.0
        self.explosive_active = False
        self.explosive_ends_at = 0.0
        self.meteors = []

    def update(self, now):
        if self.fast_attack_active and now >= self.fast_attack_ends_at:
            self.fast_attack_active = False
        if self.explosive_active and now >= self.explosive_ends_at:
            self.explosive_active = False

# meteor
class Meteor:
    def __init__(self, target_x, target_z):
        self.x = target_x
        self.z = target_z
        self.y = 10.0
        self.vy = -meteor_fall_speed
        self.radius = meteor_radius
        self.aoe = meteor_aoe_radius
        self.damage = 99999999
        self.alive = True

    def update(self, dt):
        self.y += self.vy * dt
        if self.y <= ground_y + self.radius:
            self.y = ground_y + self.radius
            self.alive = False

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

    def update(self, dt, game):
        if self.resting:
            self.time_to_next -= dt
            if self.time_to_next <= 0:
                self.resting = False
                self.boss_spawned = False
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
            return

        if not self.boss_spawned:
            self.boss_spawned = True
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
        self.yaw = 35.0
        self.pitch = 35.0

    def eye(self):
        yaw_r = math.radians(self.yaw)
        pitch_r = math.radians(self.pitch)
        cx = self.target_x + self.distance * math.cos(pitch_r) * math.sin(yaw_r)
        cy = self.target_y + self.distance * math.sin(pitch_r)
        cz = self.target_z + self.distance * math.cos(pitch_r) * math.cos(yaw_r)
        return (cx, cy, cz)

# game state
class GameState:
    def __init__(self):
        self.map = MAPS["Mohammadpur"]
        self.player = Player()
        self.abilities = Abilities()
        self.wave = WaveManager()
        self.enemies = []
        self.projectiles = []
        self.tower_slots = [TowerSlot(x, z) for (x, z) in self.map.tower_slots]
        self.camera = Camera()
        self.camera.distance = self.map.camera_distance
        self.quadric = None
        self.last_time = time.perf_counter()
        self.paused = False

# spawn
def spawn_enemy(game, speed, health):
    x0, z0 = game.map.path_points[0]
    game.enemies.append(Enemy(x0, z0, speed, health, is_boss = False))

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
        tx = sum(e.x for e in game.enemies) / len(game.enemies)
        tz = sum(e.z for e in game.enemies) / len(game.enemies)
    else:
        mid = len(game.map.path_points) // 2
        tx, tz = game.map.path_points[mid]
    game.abilities.meteors.append(Meteor(tx, tz))
    return True

# updates
def update_game(game, dt):
    now = time.perf_counter()
    game.abilities.update(now)
    game.wave.update(dt, game)
    update_enemies(game, dt)
    update_towers(game, dt)
    update_projectiles(game, dt)
    update_meteors(game, dt)

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
            t.yaw_deg = math.degrees(math.atan2(dx, dz))
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
            # impact: wipe the board; boss loses 50% of remaining HP
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
    glRotatef(t.yaw_deg, 0, 1, 0)
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
    glColor3f(0, 0, 0)
    gluSphere(quadric, m.radius, 14, 10)
    glPopMatrix()

# range debug
def draw_ranges_debug(game):
    glColor3f(0.1, 0.7, 0.1)
    segments = 32
    for slot in game.tower_slots:
        if not slot.occupied:
            continue
        t = slot.tower
        r = t.range
        for i in range(segments):
            ang0 = 2 * math.pi * (i / segments)
            ang1 = 2 * math.pi * ((i + 1) / segments)
            x0 = t.x + r * math.cos(ang0)
            z0 = t.z + r * math.sin(ang0)
            x1 = t.x + r * math.cos(ang1)
            z1 = t.z + r * math.sin(ang1)
            glBegin(GL_LINES)
            glVertex3f(x0, ground_y + 0.02, z0)
            glVertex3f(x1, ground_y + 0.02, z1)
            glEnd()

# global state
G = GameState()

# display
def display():
    glViewport(0, 0, WIDTH, HEIGHT)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(60.0, WIDTH / float(HEIGHT), 0.1, 300.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    ex, ey, ez = G.camera.eye()
    gluLookAt(ex, ey, ez, G.camera.target_x, G.camera.target_y, G.camera.target_z, 0, 1, 0)

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

    # hud
    draw_text_2d(10, HEIGHT - 24, f"Health: {G.player.health}   Money: {G.player.money}   Score: {G.player.score}   Wave: {G.wave.wave_num}   Map: {G.map.name}")
    draw_text_2d(10, HEIGHT - 48, "[1-0] Build Tower | F: Fast Fire | E: Explosive | M: Meteor | Arrows: Camera")

    glutSwapBuffers()

# idle
def idle():
    now = time.perf_counter()
    dt = now - G.last_time
    G.last_time = now
    if not G.paused:
        update_game(G, dt)
    glutPostRedisplay()

# input
def keyboard(key, x, y):
    k = key.decode('utf-8').lower()
    now = time.perf_counter()
    if k == 'p':
        G.paused = not G.paused
    elif k in '1234567890':
        idx = 9 if k == '0' else (ord(k) - ord('1'))
        build_tower_at_slot(G, idx)
    elif k == 'f':
        activate_fast_attack(G, now)
    elif k == 'e':
        activate_explosive(G, now)
    elif k == 'm':
        activate_meteor(G)
    elif k == 'q':
        import sys
        sys.exit(0)

def special(key, x, y):
    if key == GLUT_KEY_LEFT:
        G.camera.yaw -= 3
    if key == GLUT_KEY_RIGHT:
        G.camera.yaw += 3
    if key == GLUT_KEY_UP:
        G.camera.pitch = clamp(G.camera.pitch + 2, 10, 80)
    if key == GLUT_KEY_DOWN:
        G.camera.pitch = clamp(G.camera.pitch - 2, 10, 80)

def mouse(button, state, x, y):
    # no mouse picking per assignment
    pass

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
    G.player.money = float("inf")
    glutMainLoop()

if __name__ == "__main__":
    main()