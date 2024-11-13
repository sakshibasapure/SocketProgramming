#CSC573: Internet Protcols
#Contributers: Sakshi Basapure(sbasapu) and Pankhi Saini(psaini2)
#Date: Oct 17, 2024

import socket
import sys

# Check if enough command-line arguments are provided
if len(sys.argv) != 3:
    print("Usage: python auc_client.py <server_ip> <port>")
    sys.exit(1)

SERVER = sys.argv[1]  # Get the server IP from command line
PORT = int(sys.argv[2])  # Get the port number from command line and convert it to an integer


def seller_status(seller_client, msg):
    # This function checks the status of the auction request from the seller
    if msg == "Server: Invalid auction request!":
        print(msg)
        auction_request = input("Please submit auction request: ")
        seller_client.send(auction_request.encode())
        response = seller_client.recv(1024).decode()
        seller_status(seller_client, response)
    elif msg == "Server: Auction Start.":
        print("Server: Auction Start")
        return

def handle_seller(seller_client):
    print("Connected to the Auctioneer server.")
    print()
    print("Your role is: [Seller]") 
    auction_request = input("Please submit auction request: ")

    seller_client.send(auction_request.encode())
    response = seller_client.recv(1024).decode()
    
    seller_status(seller_client, response)

    while True:
        # print("Server: Auction Start.")
        response = seller_client.recv(1024).decode()
        if "Auction Start" in response:
            print(response)
            bidding_information = input()
            seller_client.send(bidding_information.encode())
            auctioneer_response = seller_client.recv(1024).decode()
            print(auctioneer_response)
            break

        elif "Auction finished" in response:
            # Auction has finished, print the notification message from the server
            print("Auction is finished. Here is the result:")
            print(response)
            break

        # Handle empty response when the server closes the connection
        if response == "":
            print("Server has closed the connection.")
            break
            

    seller_client.close()

def check_bid_status(buyer_client, msg):
    if msg == "Server: Invalid bid. Please submit a positive integer!":
        bid = input("Please submit you bid:")
        buyer_client.send(bid.encode())
        response = buyer_client.recv(1024).decode()
        check_bid_status(buyer_client, response)
    else:
        return

def handle_buyer(buyer_client):
    print("Connected to the Auctioneer server.")
    print()
    print("Your role is: [Buyer]") 

    while True:
        role_message = buyer_client.recv(1024).decode()

        # Check if the server sent an empty message (connection closed)
        if not role_message:
            print("Connection closed by the server.")
            break

        print(role_message)  # Print all messages received

        if "The bidding has started!" in role_message:
            while True:  # Continue to accept bids until a valid bid is received
                bid = input("Please submit your bid: ")
                buyer_client.send(bid.encode())
                response = buyer_client.recv(1024).decode()  # Receive the server's response
                
                # Check if the server sent an empty message (connection closed)
                if not response:
                    print("Connection closed by the server.")
                    break

                if response == "Server: Bid received. Please wait...":
                    print(response)
                    break  # Exit the inner loop once a valid bid has been submitted
                elif response == "Server: Invalid bid. Please submit a positive integer!":
                    print("Server: Invalid bid. Please submit a positive integer!")
            
            # After submitting a bid, wait for the auction results
            while True:
                auction_result = buyer_client.recv(1024).decode()  # Listen for the auction result
                
                # Check if the server sent an empty message (connection closed)
                if not auction_result:
                    print("Connection closed by the server.")
                    break
                
                # Check for the complete auction finished message for both winners and losers
                if "Auction finished!" in auction_result:
                    print(auction_result)  # Print the auction result message
                    print("Exiting after auction finished message.")
                    break  # Exit the loop after receiving the auction results

        elif "Bidding on-going" in role_message:
            print("Bidding is already in progress. You cannot join this auction.")
            buyer_client.close()
            break

    # Ensure to close the buyer_client at the end if it wasn't closed earlier
    if buyer_client:
        buyer_client.close()


if __name__ == "__main__":
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((SERVER, PORT))
    
    server_response = client_socket.recv(1024).decode()

    if server_response == 'seller':
        handle_seller(client_socket)
    elif server_response == 'buyer':
        handle_buyer(client_socket)
    else:
        print(server_response)

