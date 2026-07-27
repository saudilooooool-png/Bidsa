import { NextRequest } from "next/server";
import { establishSession } from "@/lib/authRoutes";

export async function POST(req: NextRequest) {
  return establishSession("/api/v1/auth/login", await req.json());
}
