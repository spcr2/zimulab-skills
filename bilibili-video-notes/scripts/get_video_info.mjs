#!/usr/bin/env node
/**
 * 获取B站视频元信息（无需登录）
 * 用法: node get_video_info.mjs <视频链接或BV号>
 * 输出: JSON（title, desc, owner, duration, pubdate, aid, bvid, cid, pages, multiple_pages）
 */
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';

const arg = process.argv[2];
if (!arg) {
  console.error('Usage: node get_video_info.mjs <url-or-bvid>');
  process.exit(1);
}

async function resolveBvid(input) {
  // 直接是 BV 号
  const direct = input.match(/(BV[0-9A-Za-z]{10})/);
  if (direct) return direct[1];

  let url = input.startsWith('http') ? input : `https://${input}`;
  // 短链 b23.tv 需要跟随跳转拿真实地址
  const res = await fetch(url, {
    redirect: 'follow',
    headers: { 'User-Agent': UA, 'Referer': 'https://www.bilibili.com/' },
  });
  const finalUrl = res.url || url;
  const m = finalUrl.match(/(BV[0-9A-Za-z]{10})/);
  if (!m) throw new Error(`无法从 URL 解析 BV 号: ${finalUrl}`);
  return m[1];
}

async function main() {
  const bvid = await resolveBvid(arg.trim());
  const res = await fetch(`https://api.bilibili.com/x/web-interface/view?bvid=${bvid}`, {
    headers: { 'User-Agent': UA, 'Referer': 'https://www.bilibili.com/' },
  });
  const d = await res.json();
  if (d.code !== 0) throw new Error(`API 错误: ${d.code} ${d.message}`);

  const v = d.data;
  const out = {
    bvid: v.bvid,
    aid: v.aid,
    cid: v.cid,
    title: v.title,
    desc: v.desc,
    owner: v.owner ? v.owner.name : '',
    owner_mid: v.owner ? v.owner.mid : '',
    duration_sec: v.duration,
    pubdate: v.pubdate ? new Date(v.pubdate * 1000).toISOString().slice(0, 10) : '',
    multiple_pages: v.pages && v.pages.length > 1,
    pages: (v.pages || []).map((p) => ({ cid: p.cid, part: p.part, duration: p.duration })),
    url: `https://www.bilibili.com/video/${v.bvid}/`,
  };
  console.log(JSON.stringify(out, null, 2));
}

main().catch((e) => {
  console.error(String(e));
  process.exit(1);
});
