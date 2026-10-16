import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import { getStore } from "@netlify/blobs";
import { NextRequest, NextResponse } from "next/server";
import { recoverMessageAddress } from "viem";

const COOKIE = "deepsight_session";
const SESSION_SECONDS = 8 * 60 * 60;
const CHALLENGE_SECONDS = 5 * 60;
const ADDRESS = /^0x[0-9a-f]{40}$/;
const SIGNATURE = /^0x[0-9a-f]{130}$/i;

type Challenge = { id: string; address: string; message: string; expires: number; window: number; issued: number; used: boolean };

function secret() {
  const value = process.env.DEEPSIGHT_AUTH_SECRET;
  if (!value || value.length < 32) throw new Error("Wallet sign-in is not configured.");
  return value;
}

function store() { return getStore({ name: "deepsight-auth", consistency: "strong" }); }

function webOrigin(request: NextRequest) {
  return (process.env.DEEPSIGHT_ORIGIN || new URL(request.url).origin).replace(/\/$/, "");
}

function checkOrigin(request: NextRequest) {
  const supplied = request.headers.get("origin");
  if ((supplied && supplied !== webOrigin(request)) || request.headers.get("sec-fetch-site") === "cross-site") {
    return NextResponse.json({ detail: "Request origin is not allowed" }, { status: 403 });
  }
  return null;
}

function unavailable() { return NextResponse.json({ detail: "Wallet sign-in is temporarily unavailable." }, { status: 503 }); }
function unauthorized() { return NextResponse.json({ detail: "Sign in with your wallet to continue" }, { status: 401 }); }
function denied() { return NextResponse.json({ detail: "Sign-in challenge expired or already used" }, { status: 401 }); }

function mac(payload: string) { return createHmac("sha256", secret()).update(payload).digest("hex"); }

export function readSession(token: string | undefined): string | null {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 3 || parts[0] !== "v1" || !/^[0-9a-f]{64}$/.test(parts[2])) return null;
  const payload = parts[1];
  const expected = Buffer.from(mac(payload), "hex");
  const received = Buffer.from(parts[2], "hex");
  if (!timingSafeEqual(expected, received)) return null;
  try {
    const parsed = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
    return ADDRESS.test(parsed.a) && Number.isSafeInteger(parsed.e) && parsed.e > Math.floor(Date.now() / 1000) ? parsed.a : null;
  } catch { return null; }
}

function sessionToken(address: string) {
  const payload = Buffer.from(JSON.stringify({ a: address, e: Math.floor(Date.now() / 1000) + SESSION_SECONDS })).toString("base64url");
  return `v1.${payload}.${mac(payload)}`;
}

export async function challenge(request: NextRequest) {
  const blocked = checkOrigin(request);
  if (blocked) return blocked;
  let address: string;
  try { address = String((await request.json()).address).toLowerCase(); }
  catch { return NextResponse.json({ detail: "A wallet address is required" }, { status: 400 }); }
  if (!ADDRESS.test(address)) return NextResponse.json({ detail: "Invalid wallet address" }, { status: 422 });

  try {
    secret();
    const key = `challenge/${address}`;
    const current = await store().getWithMetadata(key, { type: "json" });
    const now = Math.floor(Date.now() / 1000);
    const previous = current?.data as Challenge | undefined;
    const window = previous && now - previous.window < CHALLENGE_SECONDS ? previous.window : now;
    const issued = previous && window === previous.window ? previous.issued + 1 : 1;
    if (issued > 5) return NextResponse.json({ detail: "Too many sign-in challenges; wait five minutes" }, { status: 429 });
    const nonce = randomBytes(24).toString("hex");
    const id = `${address}-${nonce}`;
    const origin = webOrigin(request);
    const message = `${new URL(origin).host} requests a DeepSight sign-in.\nWallet: ${address}\nURI: ${origin}\nNonce: ${nonce}\nIssued at: ${now}\nExpires at: ${now + CHALLENGE_SECONDS}\nThis signature creates a research session. It does not authorize a blockchain transaction.`;
    const next: Challenge = { id, address, message, expires: now + CHALLENGE_SECONDS, window, issued, used: false };
    const saved = await store().setJSON(key, next, current?.etag ? { onlyIfMatch: current.etag } : { onlyIfNew: true });
    if (!saved.modified) return NextResponse.json({ detail: "Another challenge was requested. Please try again." }, { status: 409 });
    return NextResponse.json({ id, message }, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    console.error("Wallet challenge failed", error);
    return unavailable();
  }
}

export async function verify(request: NextRequest) {
  const blocked = checkOrigin(request);
  if (blocked) return blocked;
  let id: string, signature: string;
  try { const body = await request.json(); id = String(body.challenge_id); signature = String(body.signature); }
  catch { return NextResponse.json({ detail: "A challenge and signature are required" }, { status: 400 }); }
  const address = id.slice(0, 42);
  if (!ADDRESS.test(address) || id[42] !== "-" || !/^[0-9a-f]{48}$/.test(id.slice(43)) || !SIGNATURE.test(signature)) {
    return NextResponse.json({ detail: "Invalid sign-in proof" }, { status: 422 });
  }
  try {
    secret();
    const key = `challenge/${address}`;
    const current = await store().getWithMetadata(key, { type: "json" });
    const challenge = current?.data as Challenge | undefined;
    if (!challenge || challenge.id !== id || challenge.used || challenge.expires <= Math.floor(Date.now() / 1000) || !current?.etag) return denied();
    let recovered: string;
    try { recovered = await recoverMessageAddress({ message: challenge.message, signature: signature as `0x${string}` }); }
    catch { return NextResponse.json({ detail: "Invalid signature" }, { status: 401 }); }
    if (recovered.toLowerCase() !== address) return NextResponse.json({ detail: "Signature does not match this wallet" }, { status: 401 });
    const consumed = await store().setJSON(key, { ...challenge, used: true }, { onlyIfMatch: current.etag });
    if (!consumed.modified) return denied();
    const response = NextResponse.json({ address }, { headers: { "Cache-Control": "no-store" } });
    response.cookies.set(COOKIE, sessionToken(address), { httpOnly: true, secure: webOrigin(request).startsWith("https://"), sameSite: "strict", maxAge: SESSION_SECONDS, path: "/" });
    return response;
  } catch (error) {
    console.error("Wallet verification failed", error);
    return unavailable();
  }
}

export function session(request: NextRequest) {
  try {
    const address = readSession(request.cookies.get(COOKIE)?.value);
    return address ? NextResponse.json({ address }, { headers: { "Cache-Control": "no-store" } }) : unauthorized();
  } catch { return unavailable(); }
}

export function logout(request: NextRequest) {
  const blocked = checkOrigin(request);
  if (blocked) return blocked;
  const response = NextResponse.json({ signed_out: true }, { headers: { "Cache-Control": "no-store" } });
  response.cookies.delete(COOKIE);
  return response;
}
