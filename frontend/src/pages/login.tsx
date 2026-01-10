import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { authApi } from "@/api/client";
import { useSleepScoringStore } from "@/store";

/**
 * Login page with site password + username (honor system)
 */
export function LoginPage() {
  const navigate = useNavigate();
  const setAuth = useSleepScoringStore((state) => state.setAuth);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [authRequired, setAuthRequired] = useState<boolean | null>(null);

  // Check if auth is required on mount
  useEffect(() => {
    authApi.getAuthStatus()
      .then((status) => {
        setAuthRequired(status.auth_required);
        // If no auth required, go straight to scoring
        if (!status.auth_required) {
          setAuth("", "anonymous");
          navigate("/scoring");
        }
      })
      .catch(() => {
        // Assume auth required if we can't check
        setAuthRequired(true);
      });
  }, [navigate, setAuth]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    const formData = new FormData(e.currentTarget);
    const username = (formData.get("username") as string)?.trim() || "anonymous";
    const password = formData.get("password") as string;

    try {
      // Verify the site password
      await authApi.verifyPassword(password);

      // Store auth state (password for future API calls, username for audit)
      setAuth(password, username);

      // Navigate to scoring page (main app page)
      navigate("/scoring");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid password");
    } finally {
      setIsLoading(false);
    }
  };

  // Show loading while checking auth status
  if (authRequired === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-muted-foreground">Checking authentication...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
              <Activity className="h-6 w-6 text-primary" />
            </div>
          </div>
          <CardTitle className="text-2xl">Sleep Scoring</CardTitle>
          <CardDescription>
            Enter the site password and your name to continue
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="password">Site Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                placeholder="Enter the shared site password"
                required
                autoComplete="current-password"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="username">Your Name (optional)</Label>
              <Input
                id="username"
                name="username"
                type="text"
                placeholder="For audit logging (e.g., John)"
                autoComplete="username"
              />
              <p className="text-xs text-muted-foreground">
                This helps track who made changes. Leave blank for anonymous.
              </p>
            </div>

            {error && (
              <div className="text-sm text-destructive bg-destructive/10 px-3 py-2 rounded-md">
                {error}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "Verifying..." : "Continue"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
