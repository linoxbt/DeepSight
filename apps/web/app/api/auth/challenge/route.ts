import { NextRequest } from "next/server";
import { challenge } from "@/lib/server-auth";

export const runtime = "nodejs";
export async function POST(request: NextRequest) { return challenge(request); }
