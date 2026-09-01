using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Web.Script.Serialization;
using LabApi.Events.Arguments.ServerEvents;
using LabApi.Events.Handlers;
using LabApi.Features.Console;
using LabApi.Features.Wrappers;
using LabApi.Loader.Features.Plugins;
using LabApi.Features;

namespace SCP.SL.AutoJoiner.Companion;

public sealed class CompanionPlugin : Plugin
{
    public override string Name => "SCP:SL Auto-Joiner Companion";
    public override string Author => "MasterNazz";
    public override string Description => "Authenticated, owner-operated status endpoint for Auto-Joiner.";
    public override Version RequiredApiVersion { get; } = new Version(LabApiProperties.CompiledVersion);

    private HttpListener? listener;
    private readonly object gate = new();
    private DateTime lastRequest = DateTime.MinValue;
    private readonly HashSet<string> allowedSteamIds = new();
    private string token = "";
    private string phase = "waiting";
    private DateTime? roundStarted;

    public override void Enable()
    {
        token = Environment.GetEnvironmentVariable("SCP_SL_AUTOJOINER_COMPANION_TOKEN") ?? "";
        if (token.Length < 32)
        {
            Logger.Warn("Auto-Joiner companion disabled: configure a 32+ character bearer token.");
            return;
        }
        ConfigureAllowlist();
        ServerEvents.WaitingForPlayers += OnWaiting;
        ServerEvents.RoundStarted += OnStarted;
        ServerEvents.RoundEnded += OnEnded;
        listener = new HttpListener();
        listener.Prefixes.Add("http://127.0.0.1:42009/");
        listener.Start();
        listener.BeginGetContext(HandleContext, null);
    }

    public override void Disable()
    {
        ServerEvents.WaitingForPlayers -= OnWaiting;
        ServerEvents.RoundStarted -= OnStarted;
        ServerEvents.RoundEnded -= OnEnded;
        listener?.Close(); listener = null;
    }

    private void OnWaiting() { phase = "waiting"; roundStarted = null; }
    private void OnStarted() { phase = "running"; roundStarted = DateTime.UtcNow; }
    private void OnEnded(RoundEndedEventArgs _) { phase = "ending"; }

    private void HandleContext(IAsyncResult result)
    {
        if (listener == null || !listener.IsListening) return;
        try
        {
            var context = listener.EndGetContext(result);
            listener.BeginGetContext(HandleContext, null);
            if (context.Request.HttpMethod != "GET" || context.Request.Url?.AbsolutePath != "/v1/status")
            { context.Response.StatusCode = 404; context.Response.Close(); return; }
            var supplied = context.Request.Headers["Authorization"] ?? "";
            var valid = supplied.StartsWith("Bearer ", StringComparison.Ordinal) &&
                        CryptographicEquals(supplied.Substring(7), token);
            if (!valid) { context.Response.StatusCode = 401; context.Response.Close(); return; }
            lock (gate)
            {
                if ((DateTime.UtcNow - lastRequest).TotalSeconds < 1)
                { context.Response.StatusCode = 429; context.Response.Close(); return; }
                lastRequest = DateTime.UtcNow;
            }
            var body = BuildStatus(context.Request.Headers["X-Steam-Id"]);
            var bytes = Encoding.UTF8.GetBytes(body);
            context.Response.ContentType = "application/json";
            context.Response.ContentLength64 = bytes.Length;
            context.Response.OutputStream.Write(bytes, 0, bytes.Length);
            context.Response.Close();
        }
        catch (Exception ex) { Logger.Debug($"Auto-Joiner companion request ended: {ex.Message}"); }
    }

    private string BuildStatus(string? steamId)
    {
        var player = steamId is { Length: > 0 } && allowedSteamIds.Contains(steamId)
            ? Player.List.FirstOrDefault(p => p.UserId == steamId) : null;
        var result = new {
            protocol_version = 1,
            server = new { id = "configured-id", name = "SCP:SL Server", game_version = LabApiProperties.CompiledVersion },
            round = new { phase, started_at = roundStarted?.ToString("O") },
            capacity = new { players = Server.PlayerCount, max_players = Server.MaxPlayers },
            player = new { steam_id = player?.UserId, connected = player != null, role = player?.Role.ToString(), team = player?.Team.ToString() },
            generated_at = DateTime.UtcNow.ToString("O")
        };
        return new JavaScriptSerializer().Serialize(result);
    }

    private static bool CryptographicEquals(string left, string right)
    {
        var a = Encoding.UTF8.GetBytes(left); var b = Encoding.UTF8.GetBytes(right);
        if (a.Length != b.Length) return false;
        var difference = 0;
        for (var index = 0; index < a.Length; index++) difference |= a[index] ^ b[index];
        return difference == 0;
    }

    private void ConfigureAllowlist()
    {
        allowedSteamIds.Clear();
        var configured = Environment.GetEnvironmentVariable("SCP_SL_AUTOJOINER_ALLOWED_STEAM_IDS") ?? "";
        foreach (var value in configured.Split(new[] { ',', ';', '\n', '\r', '\t', ' ' }, StringSplitOptions.RemoveEmptyEntries))
        {
            if (value.All(char.IsDigit)) allowedSteamIds.Add(value);
        }
        Logger.Info($"Auto-Joiner companion allowlist loaded: {allowedSteamIds.Count} Steam ID(s).");
    }
}
