// AURON's head in 3D: silver, floating, no neck. It looks around on its own, follows the
// pointer a little, turns to a card when it is clicked and speaks about it.
//
// Model: "Infinite, 3D Head Scan" by Lee Perry-Smith, CC BY 3.0 (www.triplegangers.com),
// as shipped with the three.js examples. The skin texture is dropped; its normal map is
// kept, so the silver still shows pores and creases.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const MODEL = 'https://cdn.jsdelivr.net/gh/mrdoob/three.js@r160/examples/models/gltf/LeePerrySmith/LeePerrySmith.glb';
const CYAN = new THREE.Color('#4fd8ff');
const AMBER = new THREE.Color('#f2c14e');
const NECK_CUT = 0.40;   // share of the scan's height cut away from the bottom: neck and collar

function glowTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d'), r = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(.25, 'rgba(255,255,255,.75)'); r.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = r; g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

export async function mountHead(host) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  renderer.localClippingEnabled = true;
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 100);
  camera.position.set(0, 0.25, 4.9);

  scene.add(new THREE.AmbientLight(0x8fa8c8, 0.35));
  const key = new THREE.DirectionalLight(0xffffff, 1.6); key.position.set(-2, 2.5, 4); scene.add(key);
  const rim = new THREE.DirectionalLight(CYAN, 3.2); rim.position.set(3, 1, -3); scene.add(rim);
  const warm = new THREE.DirectionalLight(0xff9a3c, 1.4); warm.position.set(-3.5, -0.5, -2); scene.add(warm);
  const under = new THREE.PointLight(CYAN, 6, 6); under.position.set(0, -1.6, 0.8); scene.add(under);

  const gltf = await new GLTFLoader().loadAsync(MODEL);
  const mesh = gltf.scene.getObjectByProperty('type', 'Mesh');
  mesh.geometry.computeBoundingBox();
  const box = mesh.geometry.boundingBox, size = box.getSize(new THREE.Vector3()), centre = box.getCenter(new THREE.Vector3());
  const s = 2.2 / size.y;
  mesh.geometry.translate(-centre.x, -centre.y, -centre.z);
  mesh.geometry.scale(s, s, s);
  const h = size.y * s, w = size.x * s, d = size.z * s;

  // Silver. The scan's normal map stays for detail; colour and specular maps go.
  const cutY = -h / 2 + h * NECK_CUT;
  const cut = new THREE.Plane(new THREE.Vector3(0, 1, 0), -cutY);
  const silver = new THREE.MeshPhysicalMaterial({
    color: 0xd9dee6, metalness: 1, roughness: 0.24, clearcoat: 0.7, clearcoatRoughness: 0.18,
    normalMap: mesh.material.normalMap || null, normalScale: new THREE.Vector2(0.9, 0.9),
    envMapIntensity: 1.35, clippingPlanes: [cut], side: THREE.DoubleSide,
  });
  mesh.material = silver;

  const head = new THREE.Group();   // the part that turns
  const float = new THREE.Group();  // the part that bobs
  head.add(mesh); float.add(head); scene.add(float);

  // Where the neck is cut, a thin ring of light instead of an open edge.
  const ring = new THREE.Mesh(new THREE.TorusGeometry(1, 0.012, 8, 96),
    new THREE.MeshBasicMaterial({ color: CYAN, transparent: true, opacity: 0.9 }));
  ring.rotation.x = Math.PI / 2; ring.position.y = cutY + 0.002;
  const pos = mesh.geometry.attributes.position;
  let rx = 0, rz = 0, zMid = 0, n = 0;
  for (let i = 0; i < pos.count; i++) {
    if (Math.abs(pos.getY(i) - cutY) < h * 0.01) { rx = Math.max(rx, Math.abs(pos.getX(i))); zMid += pos.getZ(i); n++; }
  }
  if (n) {
    zMid /= n;
    for (let i = 0; i < pos.count; i++) if (Math.abs(pos.getY(i) - cutY) < h * 0.01) rz = Math.max(rz, Math.abs(pos.getZ(i) - zMid));
    ring.scale.set(rx * 1.02, rz * 1.02, 1); ring.position.z = zMid;
    head.add(ring);
  }

  // Eyes: halfway between the cut and the crown, on the face's real surface.
  const ray = new THREE.Raycaster();
  mesh.material.side = THREE.FrontSide;  // rays hit the face, not the inside of the back of the skull
  scene.updateMatrixWorld(true);         // nothing has been rendered yet: without this the ray misses everything
  const front = (x, y) => {
    ray.set(new THREE.Vector3(x, y, 10), new THREE.Vector3(0, 0, -1));
    const hit = ray.intersectObject(mesh, false)[0];
    return hit ? hit.point : null;
  };
  const eyeY = (cutY + h / 2) / 2 + h * 0.02;
  // Proportion, then the real surface: half the distance between the eyes is about 14 %
  // of the head's height from crown to chin; the glow goes onto the face right there.
  const crownToChin = h / 2 - cutY;
  const socket = (side) => front(side * 0.14 * crownToChin, eyeY);
  mesh.material.side = THREE.DoubleSide;
  const glow = glowTexture();
  const eyes = [-1, 1].map((side) => {
    const at = socket(side) || new THREE.Vector3(side * 0.12 * w, eyeY, d * 0.4);
    // a dark socket, so the light shows against bright silver, and the light inside it
    const hollow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: 0x000000, transparent: true, opacity: .75, depthWrite: false, depthTest: false }));
    hollow.scale.setScalar(0.2); hollow.position.set(at.x, at.y, at.z + 0.03); head.add(hollow);
    const mat = new THREE.SpriteMaterial({ map: glow, color: CYAN, transparent: true, depthWrite: false, depthTest: false });
    const sp = new THREE.Sprite(mat); sp.scale.setScalar(0.15);
    sp.position.set(at.x, at.y, at.z + 0.05);
    // and a halo of light around it, added on top so it blooms over the silver
    const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: CYAN, transparent: true, opacity: .55, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false }));
    halo.scale.setScalar(0.42); halo.position.copy(sp.position); head.add(halo);
    sp.userData = { side, hollow, halo };
    head.add(sp); return sp;
  });

  // --- motion ------------------------------------------------------------------
  const target = { yaw: 0, pitch: 0, until: 0 };
  const pointer = { x: 0, y: 0 };
  let speaking = false, accent = CYAN, visible = true;
  addEventListener('pointermove', (e) => { pointer.x = e.clientX / innerWidth - 0.5; pointer.y = e.clientY / innerHeight - 0.5; });
  document.addEventListener('visibilitychange', () => { visible = !document.hidden; if (visible) tick(); });

  function resize() {
    const r = host.getBoundingClientRect();
    renderer.setSize(r.width, r.height, false);
    camera.aspect = r.width / Math.max(r.height, 1); camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(host); resize();

  const clock = new THREE.Clock();
  function tick() {
    if (!visible) return;
    const t = clock.getElapsedTime(), now = performance.now();
    let yaw, pitch;
    if (now < target.until) { yaw = target.yaw; pitch = target.pitch; }
    else {
      // looking around on its own, drawn a little toward the pointer
      yaw = 0.32 * Math.sin(t * 0.21) + 0.1 * Math.sin(t * 0.67 + 1.3) + pointer.x * 0.35;
      pitch = 0.05 * Math.sin(t * 0.33) + pointer.y * 0.18;
    }
    head.rotation.y += (yaw - head.rotation.y) * 0.05;
    head.rotation.x += (pitch - head.rotation.x) * 0.05;
    float.position.y = 0.06 * Math.sin(t * 0.9);
    float.rotation.z = 0.02 * Math.sin(t * 0.5);
    const pulse = speaking ? 0.75 + 0.5 * Math.abs(Math.sin(t * 13)) * Math.random() : 0.85 + 0.15 * Math.sin(t * 2);
    eyes.forEach((e) => {
      e.scale.setScalar(0.15 * pulse);
      e.userData.halo.scale.setScalar(0.42 * pulse);
      e.material.color.copy(accent); e.userData.halo.material.color.copy(accent);
      // an eye turned away behind the face fades out instead of shining through it
      const seen = Math.max(0, Math.min(1, 1.6 - Math.max(0, e.userData.side * head.rotation.y) * 3));
      e.material.opacity = seen; e.userData.hollow.material.opacity = 0.75 * seen; e.userData.halo.material.opacity = 0.55 * seen;
    });
    ring.material.color.copy(accent); under.color.copy(accent);
    renderer.render(scene, camera);
    requestAnimationFrame(tick);
  }
  tick();

  return {
    /** Turn toward an element on the page and hold the look for a few seconds. */
    lookAt(el, holdMs = 3500) {
      const a = el.getBoundingClientRect(), b = host.getBoundingClientRect();
      const dx = (a.left + a.width / 2) - (b.left + b.width / 2), dy = (a.top + a.height / 2) - (b.top + b.height / 2);
      target.yaw = Math.max(-0.8, Math.min(0.8, dx / innerWidth * 1.8));
      target.pitch = Math.max(-0.35, Math.min(0.35, dy / innerHeight * 0.9));
      target.until = performance.now() + holdMs;
    },
    /** Say something; the eyes flicker while it speaks. */
    speak(text) {
      if (!('speechSynthesis' in window) || localStorage.getItem('auron_voice') === 'off') return;
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      const voices = speechSynthesis.getVoices();
      u.voice = voices.find((v) => /de-(DE|AT|CH)/.test(v.lang) && /male|Conrad|Stefan|Killian/i.test(v.name))
        || voices.find((v) => v.lang.startsWith('de')) || null;
      u.lang = 'de-DE'; u.rate = 1.02; u.pitch = 0.9;
      u.onstart = () => { speaking = true; }; u.onend = u.onerror = () => { speaking = false; };
      speechSynthesis.speak(u);
    },
    setDegraded(on) { accent = on ? AMBER : CYAN; },
  };
}
