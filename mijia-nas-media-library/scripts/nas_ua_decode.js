// 小米智能存储 UA 解码沙箱
// 用途：客户端 webdav 请求需要特定 User-Agent，否则 nginx 返回 451。
//       该 UA 由混淆的 userAgentInit.js generateUserAgent() 动态生成，
//       本沙箱加载真实混淆模块 + mock electron/os，让它自解码输出 UA 字符串。
//
// 前置：需先从 app.asar 提取混淆模块到某目录（含 commonUA.js / uidGenerator.js / userAgentInit.js）
//   asar 提取参考：
//     NODE_PATH=<workspace/node_modules> node -e "
//       const asar=require('@electron/asar');
//       asar.extract('~/AppData/Local/Programs/SmartStorage/resources/app.asar','./extract');"
//   然后在提取目录里找到文件名类似 commonUA.js / uidGenerator.js / userAgentInit.js 的混淆模块
//
// 用法：
//   node nas_ua_decode.js [提取目录] [uuid文件路径] [客户端版本]
//   例：node nas_ua_decode.js ~/Desktop/ss_code_extract \
//         ~/AppData/Roaming/SmartStorage/.device.uid 1.0.8
//   不带参数则用默认值（本机已验证过的路径）
const path = require('path');
const Module = require('module');
const fs = require('fs');

const EXTRACT = process.argv[2] || '~/Desktop/ss_code_extract';
const UID_FILE = process.argv[3] || '~/AppData/Roaming/SmartStorage/.device.uid';
const VERSION = process.argv[4] || '1.0.8';
const APP_DATA = path.dirname(UID_FILE);

if (!fs.existsSync(path.join(EXTRACT, 'userAgentInit.js'))) {
  console.error('[X] 提取目录缺少 userAgentInit.js:', EXTRACT);
  console.error('    请先用 @electron/asar 从 app.asar 提取混淆模块（见文件头注释）');
  process.exit(1);
}

// ---- electron mock ----
const electronMock = {
  app: {
    getPath(name) { return APP_DATA; },          // uuid 读写在它下面
    getVersion() { return VERSION; },
    getName() { return 'SmartStorage'; },
    getLocale() { return 'zh-CN'; },
    getSystemVersion() { return '10.0.22631'; },
  },
};

// ---- 万能 stub Proxy：任意属性都返回函数 ----
function makeProxyStub(name) {
  return new Proxy(function () {}, {
    get(t, prop) {
      if (prop === Symbol.toPrimitive) return () => name;
      if (prop === 'toString') return () => name;
      if (prop === 'length') return 0;
      return makeProxyStub(name + '.' + String(prop));
    },
    apply() { return undefined; },
  });
}

const loggerMock = {
  log: (...a) => console.log('[logger]', ...a),
  info: (...a) => console.log('[logger:info]', ...a),
  error: (...a) => console.log('[logger:error]', ...a),
  warn: (...a) => console.log('[logger:warn]', ...a),
  debug: (...a) => console.log('[logger:debug]', ...a),
  trace: (...a) => console.log('[logger:trace]', ...a),
};

const origLoad = Module._load;
function fallbackModule(request) {
  return new Proxy({}, {
    get(t, prop) {
      if (prop === 'getClientVersion') return () => VERSION;
      if (prop === 'logger') return loggerMock;
      if (prop === 'log') return loggerMock.log;
      if (prop === '__esModule') return false;
      if (typeof prop === 'symbol') return undefined;
      return makeProxyStub(String(prop));
    },
    apply() { return undefined; },
  });
}

Module._load = function (request, parent, isMain) {
  // 真实系统模块放行
  if (['os', 'path', 'fs', 'crypto', 'child_process', 'util', 'stream', 'events',
       'buffer', 'url', 'http', 'https', 'net', 'tls', 'zlib', 'querystring',
       'string_decoder', 'assert', 'tty', 'module'].includes(request)) {
    return origLoad.apply(this, arguments);
  }
  if (request === 'electron') return electronMock;
  try {
    const resolved = Module._resolveFilename(request, parent, isMain);
    const base = resolved.replace(/\\/g, '/');
    if (base.includes('/ss_code_extract/') || base.includes(EXTRACT.replace(/\\/g, '/'))) {
      // 真实放行：这三个自包含模块
      if (base.endsWith('commonUA.js')) return origLoad.apply(this, arguments);
      if (base.endsWith('uidGenerator.js')) return origLoad.apply(this, arguments);
      if (base.endsWith('userAgentInit.js')) return origLoad.apply(this, arguments);
      // 其余 → fallback stub
      console.log('[stub]', base.split('/').pop(), '<-', request);
      return fallbackModule(request);
    }
    return origLoad.apply(this, arguments);
  } catch (e) {
    console.log('[stub-miss]', request);
    return fallbackModule(request);
  }
};

// ---- 加载 ----
const uaMod = require(path.join(EXTRACT, 'userAgentInit.js'));
console.log('\n=== exports:', Object.keys(uaMod), '===');
try {
  const ua = uaMod.generateUserAgent();
  console.log('\n=== generateUserAgent() 返回 ===');
  console.log(JSON.stringify(ua, null, 2));
} catch (e) {
  console.log('\n[X] generateUserAgent 抛错:', e.message);
  console.log(e.stack.split('\n').slice(0, 6).join('\n'));
}
try {
  console.log('\n=== getOSInfo() ===');
  console.log(uaMod.getOSInfo());
} catch (e) {
  console.log('[X] getOSInfo 抛错:', e.message);
}
