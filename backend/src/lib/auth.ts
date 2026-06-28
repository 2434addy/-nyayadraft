import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { NextFunction, Request, Response } from "express";

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseAnonKey = process.env.SUPABASE_ANON_KEY;

// A stateless server-side client used only to validate user access tokens.
const supabase: SupabaseClient | null =
  supabaseUrl && supabaseAnonKey
    ? createClient(supabaseUrl, supabaseAnonKey, {
        auth: { persistSession: false, autoRefreshToken: false },
      })
    : null;

export interface AuthedRequest extends Request {
  userId?: string;
}

/**
 * Express middleware that requires a valid Supabase access token.
 *
 * Reads `Authorization: Bearer <jwt>`, validates it against the Supabase Auth
 * server with `getUser(token)` (which checks signature, expiry, and that the
 * user still exists), and attaches `req.userId`. Responds 401 otherwise, so
 * only authenticated users reach the generation handler.
 */
export async function requireUser(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  if (!supabase) {
    res.status(500).json({
      error: "Auth is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY.",
    });
    return;
  }

  const header = req.headers.authorization ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  if (!token) {
    res.status(401).json({ error: "Authentication required." });
    return;
  }

  try {
    const { data, error } = await supabase.auth.getUser(token);
    if (error || !data.user) {
      res
        .status(401)
        .json({ error: "Invalid or expired session. Please sign in again." });
      return;
    }
    (req as AuthedRequest).userId = data.user.id;
    next();
  } catch {
    res.status(401).json({ error: "Could not verify session." });
  }
}
