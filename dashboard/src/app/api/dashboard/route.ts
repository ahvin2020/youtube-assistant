import { NextResponse } from "next/server";
import { getDashboardData } from "@/lib/workspace";
import { getEmployees } from "@/lib/employees";

export const dynamic = "force-dynamic";

export async function GET() {
  const data = await getDashboardData();
  const employees = getEmployees(data.projects);
  return NextResponse.json({ ...data, employees });
}
