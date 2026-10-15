export interface AuthSession {
  configured: boolean;
  authenticated: boolean;
  username: string | null;
}

export interface AuthLoginResult {
  expires: number;
}
