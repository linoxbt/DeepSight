import { NextRequest } from "next/server";
import { logout, session, verify } from "@/lib/server-auth";

export const runtime = "nodejs";
export function GET(request: NextRequest) { return session(request); }
export async function POST(request: NextRequest) { return verify(request); }
export function DELETE(request: NextRequest) { return logout(request); }
