import http from 'k6/http';
import { check, sleep } from 'k6';

// --- Chức năng sinh dữ liệu ngẫu nhiên (kết hợp từ file random_data.js) ---
function seededRandom(seed) {
  let x = Math.sin(seed++) * 10000;
  return x - Math.floor(x);
}

function getRandomInt(min, max, seed) {
  min = Math.ceil(min);
  max = Math.floor(max);
  return Math.floor(seededRandom(seed) * (max - min + 1)) + min;
}

function createRandomPayload(vuIter) {
  const seed = vuIter;
  const productCount = getRandomInt(1, 3, seed);
  const products = [];

  for (let i = 0; i < productCount; i++) {
    const productId = getRandomInt(1, 3, seed + i);
    const quantity = getRandomInt(1, 5, seed + i + 10);

    products.push({
      product_id: productId,
      quantity: quantity
    });
  }

  return {
    user_id: getRandomInt(1, 100, seed + 100),
    products: products
  };
}

// --- Cấu hình chính của k6 ---
export const options = {
  stages: [
    { duration: '60s', target: 450 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<2000'],
  },
};

// --- Hàm chính thực thi kịch bản ---
export default function (data) {
  const payloadData = createRandomPayload(__VU + __ITER);
  const payload = JSON.stringify(payloadData);
  const headers = { 'Content-Type': 'application/json' };

  let res = http.post('http://order_placement:8000/place_order/', payload, {
    headers: headers,
  });

  check(res, {
    'status code is 202': (r) => r.status === 202,
  });

  sleep(1);
}